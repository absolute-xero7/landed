from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.document_parser import EXTRACTION_PROMPT, parse_document  # noqa: E402
from shared.fallbacks import build_document_fallback, merge_document_data  # noqa: E402
from shared.ircc_parser import parse_ircc_permit_text  # noqa: E402
from shared.llm_client import LLMUnavailableError, call_gpt, llm_is_configured  # noqa: E402
from shared.ocr import extract_document_text  # noqa: E402


def _guess_mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed in {"application/pdf", "image/png", "image/jpeg", "image/jpg"}:
        return guessed
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    if path.suffix.lower() == ".png":
        return "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return guessed or "application/octet-stream"


def _print_section(title: str, payload: object) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _run_gpt_structured_from_text(filename: str, text: str) -> dict:
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
            {
                "role": "user",
                "content": f"Filename: {filename}\n\n{EXTRACTION_PROMPT}\n\nDocument text:\n{text}",
            },
        ],
        max_tokens=2000,
        json_mode=True,
    )
    return json.loads(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug OCR and GPT-OSS extraction for a single immigration document.")
    parser.add_argument("path", help="Path to a PDF or image file")
    parser.add_argument("--ocr-only", action="store_true", help="Only run OCR and deterministic parsing; skip GPT structured extraction")
    parser.add_argument("--text-limit", type=int, default=2000, help="Max OCR characters to print")
    args = parser.parse_args()

    file_path = Path(args.path).expanduser().resolve()
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    mime_type = _guess_mime_type(file_path)
    file_bytes = file_path.read_bytes()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    print(f"File: {file_path}")
    print(f"MIME type: {mime_type}")
    print(f"LLM configured: {llm_is_configured()}")
    if api_key in {"", "test"}:
        print("LLM note: OPENAI_API_KEY is empty or placeholder-like; OCR/debug output is still useful, but GPT calls may fail or be misleading.")

    ocr_result = extract_document_text(file_bytes, mime_type, file_path.name)
    fallback_data = build_document_fallback(ocr_result.text, file_path.name)
    deterministic_data = parse_ircc_permit_text(ocr_result.text, file_path.name)

    _print_section(
        "OCR Summary",
        {
            "method": ocr_result.method,
            "confidence": ocr_result.confidence,
            "text_length": len(ocr_result.text),
        },
    )
    _print_section("OCR Text", ocr_result.text[: args.text_limit] or "[no text extracted]")
    _print_section("Deterministic Parser", deterministic_data or {"matched": False})
    _print_section("Fallback Parser", fallback_data)

    llm_data: dict | None = None
    if not args.ocr_only:
        if not ocr_result.text.strip():
            _print_section("GPT Structured From OCR", {"skipped": True, "reason": "OCR produced no text"})
        elif not llm_is_configured():
            _print_section("GPT Structured From OCR", {"skipped": True, "reason": "OPENAI_API_KEY is not configured"})
        else:
            try:
                llm_data = _run_gpt_structured_from_text(file_path.name, ocr_result.text)
                _print_section("GPT Structured From OCR", llm_data)
            except (LLMUnavailableError, json.JSONDecodeError) as exc:
                _print_section("GPT Structured From OCR", {"error": str(exc)})

    merged = merge_document_data(fallback_data, llm_data)
    merged = merge_document_data(deterministic_data, merged)
    _print_section("Merged Extraction", merged)
    _print_section("Full parse_document()", parse_document(file_bytes, mime_type, file_path.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
