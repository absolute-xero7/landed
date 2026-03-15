from __future__ import annotations

import base64
import json
import uuid
from datetime import date

import railtracks as rt

from models.schemas import Deadline, ExtractedDocument
from shared.fallbacks import build_document_fallback, merge_document_data
from shared.ircc_parser import parse_ircc_permit_text
from shared.llm_client import LLMUnavailableError, call_gpt
from shared.ocr import extract_document_text, extract_native_pdf_text, render_pdf_pages


EXTRACTION_PROMPT = """Extract all structured information from this immigration document.
Return ONLY valid JSON with no markdown, using exactly these keys:
{
  "document_type": one of [study_permit, trv, work_permit, ircc_letter, passport, other],
  "issuing_authority": string,
  "person_name": string,
  "dob": "YYYY-MM-DD" or null,
  "nationality": string or null,
  "visa_type": string or null,
  "permit_type": string or null,
  "employer": string or null,
  "occupation": string or null,
  "issue_date": "YYYY-MM-DD" or null,
  "expiry_date": "YYYY-MM-DD" or null,
  "conditions": [array of condition strings],
  "restrictions": [array of restriction strings],
  "reference_numbers": {"key": "value"},
  "deadlines": [{"action": string, "date": "YYYY-MM-DD", "urgency": "urgent|upcoming|future"}],
  "raw_important_text": [array of most important verbatim sentences]
}
If a field is not present use null or []. Do not add commentary."""


def _string_value(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value
    return default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    sanitized: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            sanitized[key] = item
    return sanitized


def _field_evidence_dict(value: object) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict):
        return {}

    sanitized: dict[str, dict[str, str | None]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            continue
        sanitized[key] = {
            "value": item.get("value") if isinstance(item.get("value"), str) else None,
            "confidence": item.get("confidence") if isinstance(item.get("confidence"), str) else "low",
            "source": item.get("source") if isinstance(item.get("source"), str) else "unknown",
            "excerpt": item.get("excerpt") if isinstance(item.get("excerpt"), str) else None,
        }
    return sanitized


def _extract_pdf_text(file_bytes: bytes) -> str:
    return extract_native_pdf_text(file_bytes)


def _pdf_to_image_messages(file_bytes: bytes, max_pages: int = 3) -> list[dict]:
    image_parts: list[dict] = []
    for image_bytes in render_pdf_pages(file_bytes, max_pages=max_pages):
        image_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"},
            }
        )
    return image_parts


def _field_evidence(value: object, source: str, confidence: str, excerpt: str | None = None) -> dict[str, str]:
    return {
        "value": value if isinstance(value, str) else "",
        "source": source,
        "confidence": confidence,
        "excerpt": excerpt or "",
    }


def _annotate_llm_data(data: dict, raw_text: str, extraction_method: str) -> dict:
    field_evidence: dict[str, dict[str, str]] = {}
    for key in (
        "document_type",
        "issuing_authority",
        "person_name",
        "dob",
        "nationality",
        "visa_type",
        "permit_type",
        "employer",
        "occupation",
        "issue_date",
        "expiry_date",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            field_evidence[key] = _field_evidence(value.strip(), "llm_extraction", "low", raw_text[:240])

    data["field_evidence"] = field_evidence
    data["document_confidence"] = "low"
    data["extraction_method"] = extraction_method
    data["raw_text"] = raw_text
    return data


def _looks_like_label_artifact(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return any(
        token in lowered
        for token in ("/prenom", "/citoyen", "travel doc", "given name", "family name", "temporary resident visa")
    )


def _vision_message_parts(file_bytes: bytes, mime_type: str, filename: str) -> list[dict]:
    if mime_type == "application/pdf":
        parts = _pdf_to_image_messages(file_bytes)
        parts.append(
            {
                "type": "text",
                "text": (
                    f"Filename: {filename}\n"
                    "These are rendered pages from a PDF immigration document.\n"
                    f"{EXTRACTION_PROMPT}"
                ),
            }
        )
        return parts

    b64 = base64.b64encode(file_bytes).decode()
    return [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        {"type": "text", "text": f"Filename: {filename}\n{EXTRACTION_PROMPT}"},
    ]


@rt.function_node
def parse_document(file_bytes: bytes, mime_type: str, filename: str) -> dict:
    """Parse a single immigration document using OCR first, then deterministic and LLM extraction."""
    ocr_result = extract_document_text(file_bytes, mime_type, filename)
    text_content = ocr_result.text
    fallback_data = build_document_fallback(text_content, filename)
    deterministic_data = parse_ircc_permit_text(text_content, filename)
    llm_data: dict | None = None

    try:
        should_try_llm = deterministic_data is None or deterministic_data.get("document_confidence") != "high"
        if should_try_llm and len(text_content.strip()) > 100:
            response = call_gpt(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You extract structured data from Canadian immigration documents. "
                            "Prefer exact dates, document names, conditions, and reference numbers from the source. "
                            "Do not invent names, dates, or statuses that are not present. "
                            "Return JSON only."
                        ),
                    },
                    {"role": "user", "content": f"Filename: {filename}\n\n{EXTRACTION_PROMPT}\n\nDocument text:\n{text_content}"},
                ],
                max_tokens=2000,
                json_mode=True,
            )
        elif should_try_llm:
            response = call_gpt(
                messages=[
                    {
                        "role": "user",
                        "content": _vision_message_parts(file_bytes, mime_type, filename),
                    }
                ],
                max_tokens=2000,
            )
        else:
            response = None

        if response:
            llm_data = _annotate_llm_data(json.loads(response), text_content, f"{ocr_result.method}+llm_structured")
    except (LLMUnavailableError, json.JSONDecodeError, TypeError):
        llm_data = None

    data = merge_document_data(fallback_data, llm_data)
    data = merge_document_data(deterministic_data, data)
    if data.get("document_type") != "trv":
        data["visa_type"] = None
    for field_name in ("person_name", "nationality", "visa_type"):
        if _looks_like_label_artifact(data.get(field_name)):
            data[field_name] = None if field_name != "person_name" else ""
    reference_numbers = data.get("reference_numbers", {})
    if isinstance(reference_numbers, dict):
        for key in ("travel_doc_number", "case_type"):
            value = reference_numbers.get(key)
            if isinstance(value, str) and (value.strip().upper() == "PASSPORT" or not any(char.isalnum() for char in value.strip().replace("'", ""))):
                reference_numbers.pop(key, None)
    if not data.get("extraction_method") or data.get("extraction_method") == "unknown":
        data["extraction_method"] = ocr_result.method

    today = date.today()
    deadlines: list[Deadline] = []
    for item in data.get("deadlines", []):
        try:
            deadline_date = date.fromisoformat(item["date"])
            days_remaining = (deadline_date - today).days
            urgency = "urgent" if days_remaining < 30 else ("upcoming" if days_remaining < 90 else "future")
            deadlines.append(
                Deadline(
                    action=item["action"],
                    date=item["date"],
                    urgency=urgency,
                    days_remaining=days_remaining,
                    source_document=filename,
                )
            )
        except Exception:
            continue

    return ExtractedDocument(
        document_id=str(uuid.uuid4()),
        filename=filename,
        document_type=_string_value(data.get("document_type"), "other"),
        issuing_authority=_string_value(data.get("issuing_authority")),
        person_name=_string_value(data.get("person_name")),
        dob=data.get("dob"),
        nationality=data.get("nationality"),
        visa_type=data.get("visa_type"),
        permit_type=data.get("permit_type"),
        employer=data.get("employer"),
        occupation=data.get("occupation"),
        issue_date=data.get("issue_date"),
        expiry_date=data.get("expiry_date"),
        conditions=_string_list(data.get("conditions")),
        restrictions=_string_list(data.get("restrictions")),
        reference_numbers=_string_dict(data.get("reference_numbers")),
        deadlines=deadlines,
        raw_important_text=_string_list(data.get("raw_important_text")),
        extraction_method=_string_value(data.get("extraction_method"), ocr_result.method),
        document_confidence=_string_value(data.get("document_confidence"), ocr_result.confidence),
        field_evidence=_field_evidence_dict(data.get("field_evidence")),
        raw_text=_string_value(data.get("raw_text")) or text_content,
    ).model_dump()
