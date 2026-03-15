from __future__ import annotations

import re
from datetime import date, datetime


DATE_PATTERNS = ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y")
KEY_LINE_HINTS = (
    "permit",
    "visa",
    "expiry",
    "valid until",
    "authorized",
    "action required",
    "must submit",
    "imm ",
)

DOCUMENT_TYPE_LABELS = {
    "study_permit": "study permit",
    "trv": "temporary resident visa",
    "work_permit": "work permit",
    "ircc_letter": "IRCC correspondence",
    "passport": "passport",
    "other": "uploaded document",
}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def parse_loose_date(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().rstrip(".,;:")
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def document_label(document: dict, index: int) -> str:
    document_type = document.get("document_type", "other")
    base = DOCUMENT_TYPE_LABELS.get(document_type, "uploaded document")
    return f"{base} (document {index})"


def _extract_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip().rstrip(".,;:")
    return None


def _collect_dates(text: str) -> list[str]:
    matches: list[str] = []
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}\b",
    ]
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))

    normalized: list[str] = []
    seen: set[str] = set()
    for match in matches:
        parsed = parse_loose_date(match)
        if parsed and parsed not in seen:
            seen.add(parsed)
            normalized.append(parsed)
    return normalized


def _document_type_from_text(text: str, filename: str) -> str:
    haystack = f"{text}\n{filename}".lower()
    if "correspondence" in haystack or "action required" in haystack:
        return "ircc_letter"
    if "temporary resident visa" in haystack or "visa counterfoil" in haystack or "trv" in haystack:
        return "trv"
    if "study permit" in haystack:
        return "study_permit"
    if "work permit" in haystack:
        return "work_permit"
    if "passport" in haystack:
        return "passport"
    if "ircc" in haystack:
        return "ircc_letter"
    return "other"


def _permit_type_for_document(document_type: str) -> str | None:
    mapping = {
        "study_permit": "study permit",
        "work_permit": "work permit",
    }
    return mapping.get(document_type)


def _visa_type_for_document(document_type: str) -> str | None:
    if document_type == "trv":
        return "temporary resident visa"
    return None


def _collect_conditions(text: str) -> list[str]:
    conditions: list[str] = []
    capture = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("conditions"):
            capture = True
            continue
        if capture and line.startswith("-"):
            conditions.append(line.lstrip("- ").strip())
            continue
        if capture and not line.startswith("-"):
            capture = False
        if any(token in line.lower() for token in ("authorized to", "may work", "must remain")):
            conditions.append(line)

    return list(dict.fromkeys(conditions))


def _collect_reference_numbers(text: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for label, value in re.findall(r"([A-Za-z ]+(?:Number|Reference)):\s*([A-Z0-9-]+)", text):
        key = label.strip().lower().replace(" ", "_")
        refs[key] = value.strip()
    extra_patterns = {
        "uci": [r"\bUCI[:\s]+([0-9-]{6,})"],
        "permit_number": [r"\bPermit Number[:\s]+([A-Z0-9-]+)", r"\bDocument Number[:\s]+([A-Z0-9-]+)"],
        "application_number": [r"\bApplication Number[:\s]+([A-Z0-9-]+)"],
    }
    for key, patterns in extra_patterns.items():
        if key in refs:
            continue
        value = _extract_first(patterns, text)
        if value:
            refs[key] = value
    return refs


def _important_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected = [line for line in lines if any(hint in line.lower() for hint in KEY_LINE_HINTS)]
    return selected[:6]


def _build_deadlines(text: str, filename: str, document_type: str, expiry_date: str | None) -> list[dict]:
    today = date.today()
    deadlines: list[dict] = []
    seen: set[tuple[str, str]] = set()

    if expiry_date:
        expiry_action = {
            "study_permit": "Study permit expires",
            "work_permit": "Work permit expires",
            "trv": "Temporary resident visa expires",
        }.get(document_type, "Document expires")
        seen.add((expiry_action, expiry_date))
        expiry_days = (date.fromisoformat(expiry_date) - today).days
        deadlines.append(
            {
                "action": expiry_action,
                "date": expiry_date,
                "urgency": _urgency_from_days(expiry_days),
                "days_remaining": expiry_days,
                "source_document": filename,
            }
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_dates = _collect_dates(line)
        if not line_dates:
            continue

        lowered = line.lower()
        if not any(token in lowered for token in ("must", "submit", "required", "deadline", "renew")):
            continue

        action = line
        if "trv" in lowered and "renew" in lowered:
            action = "Submit TRV renewal application"
        elif "study permit" in lowered and any(token in lowered for token in ("extend", "renew")):
            action = "Submit study permit extension"

        for deadline_date in line_dates:
            key = (action, deadline_date)
            if key in seen:
                continue
            seen.add(key)
            days_remaining = (date.fromisoformat(deadline_date) - today).days
            deadlines.append(
                {
                    "action": action,
                    "date": deadline_date,
                    "urgency": _urgency_from_days(days_remaining),
                    "days_remaining": days_remaining,
                    "source_document": filename,
                }
            )

    deadlines.sort(key=lambda item: item["date"])
    return deadlines


def _urgency_from_days(days_remaining: int) -> str:
    if days_remaining < 30:
        return "urgent"
    if days_remaining < 90:
        return "upcoming"
    return "future"


def _make_evidence(value: object, confidence: str, source: str, excerpt: str | None = None) -> dict[str, str]:
    return {
        "value": value if isinstance(value, str) else "",
        "confidence": confidence,
        "source": source,
        "excerpt": excerpt or "",
    }


def _is_populated(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "other"
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _confidence_score(evidence: dict | None) -> int:
    if not isinstance(evidence, dict):
        return -1
    return CONFIDENCE_ORDER.get(str(evidence.get("confidence", "low")).lower(), -1)


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _best_identity(documents: list[dict]) -> str | None:
    best_value: str | None = None
    best_score = -1
    for document in documents:
        candidate = _clean_string(document.get("person_name"))
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(token in lowered for token in ("/prenom", "/citoyen", "travel doc", "given name")):
            continue
        score = _confidence_score(document.get("field_evidence", {}).get("person_name"))
        if score > best_score:
            best_value = candidate
            best_score = score
    return best_value


def _current_status_document(documents: list[dict]) -> dict | None:
    permit_docs = [document for document in documents if document.get("document_type") in {"study_permit", "work_permit"}]
    if not permit_docs:
        return None

    dated_docs: list[tuple[dict, date, bool, int]] = []
    for document in permit_docs:
        expiry = parse_loose_date(document.get("expiry_date"))
        if not expiry:
            continue
        expiry_date = date.fromisoformat(expiry)
        dated_docs.append(
            (
                document,
                expiry_date,
                expiry_date >= date.today(),
                _confidence_score(document.get("field_evidence", {}).get("expiry_date")),
            )
        )

    if dated_docs:
        active_docs = [item for item in dated_docs if item[2]]
        if active_docs:
            active_docs.sort(key=lambda item: (item[1], item[3]), reverse=True)
            return active_docs[0][0]
        dated_docs.sort(key=lambda item: (item[1], item[3]), reverse=True)
        return dated_docs[0][0]

    return sorted(
        permit_docs,
        key=lambda document: (
            _confidence_score(document.get("field_evidence", {}).get("document_type")),
            _confidence_score(document.get("field_evidence", {}).get("person_name")),
        ),
        reverse=True,
    )[0]


def _authorized_activity_lines(document: dict | None) -> list[str]:
    if not document:
        return []

    activities: list[str] = []
    for condition in document.get("conditions", []):
        if not isinstance(condition, str):
            continue
        lowered = condition.lower()
        if any(token in lowered for token in ("must leave", "not valid for employment", "cease working")):
            continue
        cleaned = re.split(
            r"\b(?:must leave|must\b|not valid for employment|cease working|employment practicum cannot)\b",
            condition,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        cleaned = " ".join(cleaned.split()).strip(" .,;:-")
        if any(token in cleaned.lower() for token in ("may ", "authorized", "work", "study", "employment")):
            if cleaned and cleaned not in activities:
                activities.append(cleaned)
    return activities


def build_document_fallback(text: str, filename: str) -> dict:
    document_type = _document_type_from_text(text, filename)
    issue_date = parse_loose_date(_extract_first([r"Issue Date:\s*([^\n]+)", r"Valid From[:\s]*([^\n]+)"], text))
    expiry_match = _extract_first(
        [
            r"valid until\s+(\d{4}-\d{2}-\d{2})",
            r"Expires?[:\s]*(\d{4}-\d{2}-\d{2})",
            r"Valid Until[:\s]*(\d{4}-\d{2}-\d{2})",
            r"Expiry Date:\s*([^\n]+)",
            r"Expires?[:\s]*([^\n]+)",
            r"Valid Until[:\s]*([^\n]+)",
            r"valid until ([^\n.]+)",
            r"valid until ([^,]+\d{4})",
        ],
        text,
    )
    expiry_date = parse_loose_date(expiry_match)

    person_name = _extract_first(
        [
            r"Name:\s*([^\n]+)",
            r"Given Name\(s\)[:\s]*([^\n]+)",
            r"Client Name:\s*([^\n]+)",
            r"Dear\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)",
        ],
        text,
    ) or ""

    nationality = _extract_first([r"Nationality:\s*([^\n]+)", r"Country of Citizenship[:\s]*([^\n]+)"], text)
    dob = parse_loose_date(_extract_first([r"Date of Birth:\s*([^\n]+)"], text))
    issuing_authority = "IRCC" if "ircc" in text.lower() or document_type != "other" else ""
    conditions = _collect_conditions(text)
    employer = _extract_first([r"Employer[:\s]*([^\n]+)"], text)
    occupation = _extract_first([r"Occupation[:\s]*([^\n]+)"], text)
    evidence: dict[str, dict[str, str]] = {}

    if document_type != "other":
        evidence["document_type"] = _make_evidence(document_type, "medium", "filename_or_text_match", filename)
        if permit_type := _permit_type_for_document(document_type):
            evidence["permit_type"] = _make_evidence(permit_type, "medium", "filename_or_text_match", filename)
        if visa_type := _visa_type_for_document(document_type):
            evidence["visa_type"] = _make_evidence(visa_type, "medium", "filename_or_text_match", filename)
    if issuing_authority:
        evidence["issuing_authority"] = _make_evidence(issuing_authority, "medium", "issuer_hint", "IRCC")
    if person_name:
        evidence["person_name"] = _make_evidence(person_name, "medium", "regex_match", person_name)
    if dob:
        evidence["dob"] = _make_evidence(dob, "medium", "regex_match", "Date of Birth")
    if nationality:
        evidence["nationality"] = _make_evidence(nationality, "medium", "regex_match", nationality)
    if issue_date:
        evidence["issue_date"] = _make_evidence(issue_date, "medium", "regex_match", "Issue Date")
    if expiry_date:
        evidence["expiry_date"] = _make_evidence(expiry_date, "medium", "regex_match", expiry_match)
    if employer:
        evidence["employer"] = _make_evidence(employer, "medium", "regex_match", employer)
    if occupation:
        evidence["occupation"] = _make_evidence(occupation, "medium", "regex_match", occupation)

    return {
        "document_type": document_type,
        "issuing_authority": issuing_authority,
        "person_name": person_name,
        "dob": dob,
        "nationality": nationality,
        "visa_type": _visa_type_for_document(document_type),
        "permit_type": _permit_type_for_document(document_type),
        "employer": employer,
        "occupation": occupation,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "conditions": conditions,
        "restrictions": [],
        "reference_numbers": _collect_reference_numbers(text),
        "deadlines": _build_deadlines(text, filename, document_type, expiry_date),
        "raw_important_text": _important_lines(text),
        "field_evidence": evidence,
        "document_confidence": "medium" if document_type != "other" else "low",
        "extraction_method": "regex_fallback",
        "raw_text": text,
    }


def merge_document_data(primary: dict | None, secondary: dict | None) -> dict:
    """Merge extracted document payloads, preferring higher-confidence field evidence."""
    primary = primary or {}
    secondary = secondary or {}
    merged = dict(secondary)

    merged_evidence: dict[str, dict] = {}
    for source in (secondary.get("field_evidence", {}), primary.get("field_evidence", {})):
        if not isinstance(source, dict):
            continue
        for key, evidence in source.items():
            if not isinstance(key, str) or not isinstance(evidence, dict):
                continue
            existing = merged_evidence.get(key)
            if existing is None or _confidence_score(evidence) >= _confidence_score(existing):
                merged_evidence[key] = evidence

    scalar_keys = (
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
    )
    for key in scalar_keys:
        chosen_value = None
        chosen_evidence = None
        for candidate_index, candidate in enumerate((secondary, primary)):
            value = candidate.get(key)
            if not _is_populated(value):
                continue
            candidate_evidence = candidate.get("field_evidence", {}).get(key, {})
            if key == "document_type" and str(value).strip() == "other":
                continue
            if chosen_evidence is None or _confidence_score(candidate_evidence) > _confidence_score(chosen_evidence):
                chosen_value = value
                chosen_evidence = candidate_evidence
            elif _confidence_score(candidate_evidence) == _confidence_score(chosen_evidence):
                if not _is_populated(chosen_value) or candidate_index == 1:
                    chosen_value = value
                    chosen_evidence = candidate_evidence
        if _is_populated(chosen_value):
            merged[key] = chosen_value

    for key in ("conditions", "restrictions", "raw_important_text"):
        values: list[str] = []
        for source in (secondary.get(key, []), primary.get(key, [])):
            if not isinstance(source, list):
                continue
            for item in source:
                if isinstance(item, str) and item.strip() and item not in values:
                    values.append(item.strip())
        merged[key] = values

    reference_numbers: dict[str, str] = {}
    for source in (secondary.get("reference_numbers", {}), primary.get("reference_numbers", {})):
        if not isinstance(source, dict):
            continue
        for ref_key, ref_value in source.items():
            if isinstance(ref_key, str) and isinstance(ref_value, str) and ref_value.strip():
                reference_numbers[ref_key] = ref_value.strip()
    merged["reference_numbers"] = reference_numbers

    deadlines: list[dict] = []
    seen_deadlines: set[tuple[str, str, str]] = set()
    for source in (secondary.get("deadlines", []), primary.get("deadlines", [])):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            deadline_date = item.get("date")
            source_document = item.get("source_document", "")
            if not isinstance(action, str) or not isinstance(deadline_date, str):
                continue
            dedupe_key = (action, deadline_date, source_document if isinstance(source_document, str) else "")
            if dedupe_key in seen_deadlines:
                continue
            seen_deadlines.add(dedupe_key)
            deadlines.append(item)
    deadlines.sort(key=lambda item: item.get("date", ""))
    merged["deadlines"] = deadlines
    merged["field_evidence"] = merged_evidence

    methods = [method for method in (secondary.get("extraction_method"), primary.get("extraction_method")) if isinstance(method, str) and method]
    merged["extraction_method"] = "+".join(dict.fromkeys(methods)) if methods else "unknown"

    raw_text = primary.get("raw_text") if isinstance(primary.get("raw_text"), str) and primary.get("raw_text", "").strip() else secondary.get("raw_text")
    if isinstance(raw_text, str):
        merged["raw_text"] = raw_text

    confidence_candidates = [
        str(secondary.get("document_confidence", "low")).lower(),
        str(primary.get("document_confidence", "low")).lower(),
    ]
    for key in ("document_type", "person_name", "expiry_date"):
        if key in merged_evidence:
            confidence_candidates.append(str(merged_evidence[key].get("confidence", "low")).lower())
    merged["document_confidence"] = max(confidence_candidates, key=lambda item: CONFIDENCE_ORDER.get(item, 0))

    return merged


def build_profile_fallback(documents: list[dict]) -> dict:
    if not documents:
        return {
            "current_status": "Unable to determine immigration status from the uploaded documents.",
            "permit_type": "unknown",
            "authorized_activities": [],
            "expiry_date": "",
            "days_until_expiry": 0,
            "urgency_level": "normal",
            "all_deadlines": [],
            "required_actions": [],
            "risks": [],
        }

    deadlines: list[dict] = []
    seen_deadlines: set[tuple[str, str, str]] = set()
    expiry_candidates: list[tuple[date, str, dict]] = []
    all_authorized_activities: list[str] = []
    permit_type = "unknown"

    for document in documents:
        if permit_type == "unknown":
            permit_type = document.get("permit_type") or permit_type

        for condition in document.get("conditions", []):
            if condition not in all_authorized_activities:
                all_authorized_activities.append(condition)

        expiry_date = parse_loose_date(document.get("expiry_date"))
        if expiry_date:
            expiry_candidates.append(
                (
                    date.fromisoformat(expiry_date),
                    expiry_date,
                    document,
                )
            )

        for deadline in document.get("deadlines", []):
            key = (deadline["action"], deadline["date"], deadline["source_document"])
            if key in seen_deadlines:
                continue
            seen_deadlines.add(key)
            deadlines.append(deadline)

    deadlines.sort(key=lambda item: item["date"])
    expiry_candidates.sort(key=lambda item: item[0])
    current_doc = _current_status_document(documents)
    reliable_identity = _best_identity(documents)
    if current_doc and current_doc.get("permit_type"):
        permit_type = current_doc.get("permit_type") or permit_type

    current_expiry = parse_loose_date(current_doc.get("expiry_date")) if current_doc else None
    nearest_date = date.fromisoformat(current_expiry) if current_expiry else None
    if nearest_date is None:
        future_deadlines = [item for item in deadlines if date.fromisoformat(item["date"]) >= date.today()]
        if future_deadlines:
            future_deadlines.sort(key=lambda item: item["date"])
            nearest_date = date.fromisoformat(future_deadlines[0]["date"])
            current_expiry = future_deadlines[0]["date"]
        elif expiry_candidates:
            expiry_candidates.sort(key=lambda item: item[0], reverse=True)
            nearest_date = expiry_candidates[0][0]
            current_expiry = expiry_candidates[0][1]
        elif deadlines:
            nearest_date = date.fromisoformat(deadlines[0]["date"])
            current_expiry = deadlines[0]["date"]

    days_until_expiry = (nearest_date - date.today()).days if nearest_date else 0
    urgency_level = "critical" if days_until_expiry < 30 else ("urgent" if days_until_expiry <= 60 else "normal")

    document_types = {doc.get("document_type") for doc in documents}
    risks: list[str] = []
    required_actions: list[dict] = []
    current_doc_type_confident = bool(
        current_doc and _confidence_score(current_doc.get("field_evidence", {}).get("document_type")) >= CONFIDENCE_ORDER["medium"]
    )
    current_doc_expiry_confident = bool(
        current_doc
        and parse_loose_date(current_doc.get("expiry_date"))
        and _confidence_score(current_doc.get("field_evidence", {}).get("expiry_date")) >= CONFIDENCE_ORDER["medium"]
    )
    uncertain_core = not reliable_identity or not current_doc_type_confident or not current_doc_expiry_confident

    authorized_activities = _authorized_activity_lines(current_doc) if current_doc else all_authorized_activities

    if "trv" in document_types:
        trv_doc = next((doc for doc in documents if doc.get("document_type") == "trv"), None)
        permit_doc = next(
            (
                doc
                for doc in documents
                if doc.get("document_type") in {"study_permit", "work_permit"} and doc.get("expiry_date")
            ),
            None,
        )
        if trv_doc and trv_doc.get("expiry_date"):
            required_actions.append(
                {
                    "action_id": "trv_renewal",
                    "title": "Renew temporary resident visa",
                    "urgency": _urgency_from_days((date.fromisoformat(trv_doc["expiry_date"]) - date.today()).days),
                    "deadline": trv_doc["expiry_date"],
                    "steps": [],
                }
            )
        if trv_doc and permit_doc and trv_doc.get("expiry_date") and permit_doc.get("expiry_date"):
            trv_expiry = date.fromisoformat(trv_doc["expiry_date"])
            permit_expiry = date.fromisoformat(permit_doc["expiry_date"])
            if trv_expiry < permit_expiry:
                risks.append("Your TRV expires before your underlying permit, which can block re-entry to Canada.")

    if permit_type in {"study permit", "work permit"}:
        matching_doc = current_doc if current_doc and current_doc.get("permit_type") == permit_type and current_doc.get("expiry_date") else next(
            (doc for doc in documents if doc.get("permit_type") == permit_type and doc.get("expiry_date")),
            None,
        )
        if matching_doc and matching_doc.get("expiry_date"):
            expiry_days = (date.fromisoformat(matching_doc["expiry_date"]) - date.today()).days
            if expiry_days < 0:
                required_actions.append(
                    {
                        "action_id": "verify_current_status",
                        "title": "Verify whether a newer permit or extension filing exists",
                        "urgency": _urgency_from_days(expiry_days),
                        "deadline": matching_doc["expiry_date"],
                        "steps": [
                            {
                                "step_number": 1,
                                "instruction": "Check whether a newer permit, extension approval, or maintained-status filing exists after this uploaded document.",
                                "form_name": None,
                                "form_number": None,
                                "official_link": None,
                                "fee": None,
                                "processing_time": None,
                                "tip": "Do not rely on this document alone if other filings or approvals exist.",
                            },
                            {
                                "step_number": 2,
                                "instruction": "Gather the current permit, passport, IRCC letters, and any submission or payment confirmations tied to status renewal or restoration.",
                                "form_name": None,
                                "form_number": None,
                                "official_link": None,
                                "fee": None,
                                "processing_time": None,
                                "tip": None,
                            },
                            {
                                "step_number": 3,
                                "instruction": "If no newer status document exists, review restoration or a new status application path before relying on work or travel plans.",
                                "form_name": None,
                                "form_number": None,
                                "official_link": None,
                                "fee": None,
                                "processing_time": None,
                                "tip": None,
                            },
                        ],
                    }
                )
            elif expiry_days <= 120:
                required_actions.append(
                    {
                        "action_id": "permit_extension",
                        "title": f"Prepare {permit_type} extension",
                        "urgency": _urgency_from_days(expiry_days),
                        "deadline": matching_doc["expiry_date"],
                        "steps": [],
                    }
                )

    if not required_actions and deadlines:
        first_deadline = deadlines[0]
        required_actions.append(
            {
                "action_id": "deadline_follow_up",
                "title": first_deadline["action"],
                "urgency": first_deadline["urgency"],
                "deadline": first_deadline["date"],
                "steps": [],
            }
        )

    if not authorized_activities and permit_type == "study permit":
        authorized_activities.append("Study full-time at a designated learning institution.")

    subject = reliable_identity or "This person"
    if permit_type == "study permit":
        if current_expiry:
            current_status = (
                f"{subject}'s uploaded study permit shows an expiry date of {current_expiry}. "
                "This summary only reflects the documents uploaded here."
            )
        else:
            current_status = "A study permit appears in the uploaded documents, but the key status dates could not be verified."
        if "trv" in document_types:
            current_status += " Temporary resident visa timing should be reviewed separately from the permit."
    elif permit_type == "work permit":
        if current_expiry:
            current_status = (
                f"{subject}'s uploaded work permit shows an expiry date of {current_expiry}. "
                "Landed cannot confirm from this upload alone whether a newer permit, extension filing, or maintained status exists."
            )
        else:
            current_status = "A work permit appears in the uploaded documents, but the key status dates could not be verified."
    else:
        current_status = "Temporary resident status identified from uploaded documents."

    if uncertain_core:
        risks.append("Some key identity or document fields were not verified confidently from the uploaded documents.")
    if current_doc and parse_loose_date(current_doc.get("expiry_date")):
        current_expiry_date = date.fromisoformat(parse_loose_date(current_doc.get("expiry_date")) or current_doc["expiry_date"])
        if current_expiry_date < date.today():
            risks.append("At least one uploaded status document appears expired, but a newer approval or filing may exist outside this upload.")

    expiry_date = current_expiry.isoformat() if isinstance(current_expiry, date) else (current_expiry or (deadlines[0]["date"] if deadlines else ""))
    return {
        "current_status": current_status,
        "permit_type": permit_type,
        "authorized_activities": authorized_activities,
        "expiry_date": expiry_date,
        "days_until_expiry": days_until_expiry,
        "urgency_level": urgency_level,
        "all_deadlines": deadlines,
        "required_actions": required_actions,
        "risks": risks,
    }


def build_grounded_qa_answer(
    question: str,
    profile: dict,
    documents: list[dict],
    work_authorization: dict | None = None,
    document_completeness: dict | None = None,
) -> str | None:
    question_lower = question.lower()

    indexed_documents = list(enumerate(documents, start=1))

    def find_document(document_type: str) -> tuple[int, dict] | None:
        return next(((index, doc) for index, doc in indexed_documents if doc.get("document_type") == document_type), None)

    def source_for_work_authorization() -> str:
        if isinstance(work_authorization, dict):
            source_filename = work_authorization.get("source_document")
            if isinstance(source_filename, str):
                for index, document in indexed_documents:
                    if document.get("filename") == source_filename:
                        return document_label(document, index)
        study_match = find_document("study_permit")
        if study_match:
            index, document = study_match
            return document_label(document, index)
        work_match = find_document("work_permit")
        if work_match:
            index, document = work_match
            return document_label(document, index)
        return document_label(documents[0], 1) if documents else "uploaded documents"

    if any(token in question_lower for token in ("name", "who is this", "whose")):
        for index, document in indexed_documents:
            person_name = document.get("person_name")
            if isinstance(person_name, str) and person_name.strip():
                return f"The uploaded documents identify this person as {person_name.strip()}. Source: {document_label(document, index)}."

    if any(token in question_lower for token in ("travel", "re-enter", "reenter", "come back", "leave canada", "return to canada")):
        trv_match = find_document("trv")
        permit_match = find_document("study_permit") or find_document("work_permit")
        if trv_match:
            index, document = trv_match
            expiry = document.get("expiry_date")
            if expiry:
                answer = f"The uploaded TRV appears valid until {expiry}."
                if permit_match:
                    answer += " Re-entry also depends on the underlying permit remaining valid."
                return f"{answer} Source: {document_label(document, index)}."
        if permit_match:
            index, document = permit_match
            return (
                f"I could not verify a TRV from the uploaded documents, so I cannot confirm re-entry authorization after international travel. "
                f"Source: {document_label(document, index)}."
            )

    if any(token in question_lower for token in ("implied status", "maintained status", "apply before expiry", "after expiry while waiting")):
        actions = profile.get("required_actions", [])
        for action in actions:
            implied = action.get("implied_status")
            if isinstance(implied, dict) and implied.get("explanation"):
                answer = str(implied["explanation"]).strip()
                warning = implied.get("warning")
                if isinstance(warning, str) and warning.strip():
                    answer += f" {warning.strip()}"
                return answer

    if any(token in question_lower for token in ("status", "situation", "where do i stand", "can i stay", "what is my current")):
        status = profile.get("current_status")
        if isinstance(status, str) and status.strip():
            source = source_for_work_authorization() if profile.get("permit_type") in {"study permit", "work permit"} else (document_label(documents[0], 1) if documents else "uploaded documents")
            return f"{status.strip()} Source: {source}."

    if any(token in question_lower for token in ("missing documents", "documents are missing", "what documents are missing", "missing upload", "complete analysis", "which documents", "what documents")):
        if isinstance(document_completeness, dict):
            missing = document_completeness.get("missing", [])
            if isinstance(missing, list) and missing:
                first = missing[0]
                if isinstance(first, dict):
                    doc_type = first.get("type", "another document")
                    reason = first.get("reason", "it would help complete the analysis")
                    return f"For a more complete analysis, consider uploading a {doc_type}. {reason}"
            if document_completeness.get("complete") is True:
                return "The uploaded document set appears complete for the recommended analysis."

    if any(token in question_lower for token in ("expire", "expiry", "valid until")):
        for label, document_type in (("TRV", "trv"), ("study permit", "study_permit"), ("work permit", "work_permit")):
            if label.lower() in question_lower:
                match = find_document(document_type)
                if match:
                    index, document = match
                    if document.get("expiry_date"):
                        return f"Your {label} appears valid until {document['expiry_date']}. Source: {document_label(document, index)}."

        for index, document in indexed_documents:
            if document.get("expiry_date"):
                return f"The nearest expiry I found is {document['expiry_date']}. Source: {document_label(document, index)}."

    if any(token in question_lower for token in ("miss this", "what happens if", "if i miss", "consequence", "miss deadline", "miss my deadline")):
        deadlines = profile.get("all_deadlines", [])
        if deadlines:
            deadline = deadlines[0]
            consequence = deadline.get("consequence")
            action = deadline.get("consequence_action")
            source_label = next(
                (document_label(doc, index) for index, doc in indexed_documents if doc.get("filename") == deadline.get("source_document")),
                deadline.get("source_document", "uploaded documents"),
            )
            if consequence:
                answer = str(consequence).strip()
                if action:
                    answer += f" Recommended action: {str(action).strip()}"
                return f"{answer} Source: {source_label}."

    if any(token in question_lower for token in ("risk", "problem", "issue", "wrong", "conflict")):
        risks = profile.get("risks", [])
        if risks:
            source = source_for_work_authorization() if documents else "uploaded documents"
            return f"The main risk I found is: {risks[0]} Source: {source}."

    if any(token in question_lower for token in ("work", "campus", "job", "employment", "hours", "co-op", "coop", "break")):
        if isinstance(work_authorization, dict) and isinstance(work_authorization.get("authorized"), bool):
            source = source_for_work_authorization()
            if work_authorization.get("authorized") is False:
                return f"The uploaded documents indicate this person is not authorized to work under the current conditions. Source: {source}."

            if any(token in question_lower for token in ("on campus", "on-campus")):
                if work_authorization.get("on_campus"):
                    return f"On-campus work appears authorized if this person remains otherwise eligible under the study permit conditions. Source: {source}."
                return f"I could not verify on-campus work authorization from the uploaded documents. Source: {source}."

            if any(token in question_lower for token in ("off campus", "off-campus", "how long", "hours", "part-time")):
                hours = work_authorization.get("off_campus_hours_per_week")
                if isinstance(hours, int):
                    answer = (
                        f"This person may work up to {hours} hours per week off campus during regular academic sessions if otherwise eligible."
                    )
                    if work_authorization.get("full_time_during_breaks"):
                        answer += " Full-time work during scheduled breaks also appears authorized."
                    return f"{answer} Source: {source}."

            if any(token in question_lower for token in ("break", "holiday")):
                if work_authorization.get("full_time_during_breaks"):
                    return f"Yes. Full-time work during scheduled breaks appears authorized if the other study permit conditions are met. Source: {source}."
                return f"I could not verify a scheduled-break work rule from the uploaded documents. Source: {source}."

            if any(token in question_lower for token in ("co-op", "coop", "practicum")):
                if work_authorization.get("coop_authorized"):
                    return f"Co-op or practicum work appears authorized in the uploaded documents. Source: {source}."
                return f"I could not verify co-op or practicum work authorization from the uploaded documents. Source: {source}."

            plain_english = work_authorization.get("plain_english")
            if isinstance(plain_english, str) and plain_english.strip():
                return f"{plain_english.strip()} Source: {source}."

        preferred_types = ("study_permit", "work_permit")
        for preferred_type in preferred_types:
            match = find_document(preferred_type)
            if not match:
                continue
            index, document = match
            work_conditions = [line for line in document.get("conditions", []) if "work" in line.lower()]
            if work_conditions:
                return f"{work_conditions[0]} Source: {document_label(document, index)}."

    if any(token in question_lower for token in ("next", "do", "action", "deadline", "renew")):
        actions = profile.get("required_actions", [])
        if actions:
            action = actions[0]
            deadline = action.get("deadline") or "no explicit deadline found"
            return f"Next recommended step: {action['title']}. Deadline: {deadline}."
        deadlines = profile.get("all_deadlines", [])
        if deadlines:
            deadline = deadlines[0]
            source_label = next(
                (document_label(doc, index) for index, doc in indexed_documents if doc.get("filename") == deadline["source_document"]),
                deadline["source_document"],
            )
            return f"The next deadline I found is {deadline['action']} by {deadline['date']}. Source: {source_label}."

    return None
def build_qa_fallback(
    question: str,
    profile: dict,
    documents: list[dict],
    work_authorization: dict | None = None,
    document_completeness: dict | None = None,
) -> str:
    grounded = build_grounded_qa_answer(question, profile, documents, work_authorization, document_completeness)
    if grounded:
        return grounded

    sources = ", ".join(document_label(doc, index) for index, doc in enumerate(documents, start=1)) or "uploaded documents"
    status = profile.get("current_status") or "I could not determine a clear status"
    if profile.get("risks"):
        return f"{status} Main risk: {profile['risks'][0]} Sources: {sources}."
    return f"{status} I can only answer from the uploaded documents. Sources: {sources}."
