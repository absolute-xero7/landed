from __future__ import annotations

import re
import unicodedata

from shared.fallbacks import parse_loose_date


def _evidence(value: str | None, source: str, excerpt: str | None, confidence: str = "high") -> dict[str, str]:
    return {
        "value": value or "",
        "source": source,
        "excerpt": excerpt or "",
        "confidence": confidence,
    }


def _compact_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))


def _fold_text(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


def _search(patterns: list[str], text: str, folded_text: str | None = None) -> tuple[str | None, str | None]:
    for candidate_text in (text, folded_text):
        if not candidate_text:
            continue
        for pattern in patterns:
            match = re.search(pattern, candidate_text, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip(), match.group(0).strip()
    return None, None


def _normalized_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_label_line(line: str) -> bool:
    folded = _fold_text(line).lower()
    label_hints = (
        "family name",
        "given name",
        "date of birth",
        "country of birth",
        "country of citizenship",
        "travel doc",
        "date issued",
        "expiry date",
        "case type",
        "institution name",
        "field of study",
        "level of study",
        "in force from",
        "employer",
        "occupation",
        "conditions",
        "remarks/observations",
        "client information",
        "additional information",
    )
    return any(hint in folded for hint in label_hints)


def _next_value_after_label(lines: list[str], label_patterns: list[str], max_offset: int = 5) -> tuple[str | None, str | None]:
    for index, line in enumerate(lines):
        folded_line = _fold_text(line)
        if not any(re.search(pattern, folded_line, flags=re.IGNORECASE) for pattern in label_patterns):
            continue

        same_line_match = re.search(r":\s*(.+)$", line)
        if same_line_match and same_line_match.group(1).strip():
            return same_line_match.group(1).strip(), line

        for offset in range(1, max_offset + 1):
            candidate_index = index + offset
            if candidate_index >= len(lines):
                break
            candidate = lines[candidate_index].strip()
            if not candidate:
                continue
            if _is_label_line(candidate):
                break
            if re.fullmatch(r"\(.*\)", candidate):
                continue
            return candidate, f"{line}\n{candidate}"
    return None, None


def _header_name(lines: list[str]) -> tuple[str | None, str | None]:
    for index, line in enumerate(lines[:12]):
        if not re.fullmatch(r"[A-Z][A-Z' -]+", line):
            continue
        if any(token in line for token in ("CANADA", "PROTECTED", "STUDY PERMIT", "WORK PERMIT")):
            continue
        parts = [part for part in line.split() if part]
        if len(parts) >= 2:
            return " ".join(part.title() for part in parts), line
        if index + 1 < len(lines) and re.fullmatch(r"[A-Z][A-Z' -]+", lines[index + 1]):
            combined = f"{line} {lines[index + 1]}"
            return " ".join(part.title() for part in combined.split()), f"{line}\n{lines[index + 1]}"
    return None, None


def _looks_like_label_artifact(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(
        token in lowered
        for token in (
            "/prenom",
            "travel doc",
            "/citoyen",
            "date of birth",
            "given name",
            "family name",
            "temporary resident visa",
        )
    )


def _extract_named_date(patterns: list[str], text: str, folded_text: str) -> tuple[str | None, str | None]:
    value, excerpt = _search(patterns, text, folded_text)
    if value:
        parsed = parse_loose_date(value.replace(".", "/"))
        return parsed or value.replace("/", "-"), excerpt
    return None, None


def _parse_name(text: str, folded_text: str) -> tuple[str | None, dict[str, dict]]:
    family_name, family_excerpt = _search(
        [
            r"Family Name/Nom de Famille:\s*([A-Z][A-Z' -]+)",
            r"Family Name\s*/\s*Nom de Famille:\s*([^\n]+)",
        ],
        text,
        folded_text,
    )
    given_names, given_excerpt = _search(
        [
            r"Given Name\(s\)/Pr[ée]nom\(s\):\s*([A-Z][A-Z' -]+)",
            r"Given Name\(s\)\s*/\s*Pr[ée]nom\(s\):\s*([^\n]+)",
        ],
        text,
        folded_text,
    )

    evidence: dict[str, dict] = {}
    if family_name:
        family_name = " ".join(family_name.split())
    if given_names:
        given_names = " ".join(given_names.split())

    if family_name and given_names:
        person_name = f"{given_names.title()} {family_name.title()}"
        evidence["person_name"] = _evidence(person_name, "label_match", f"{given_excerpt}\n{family_excerpt}")
        return person_name, evidence

    lines = _normalized_lines(text)
    family_value, family_excerpt = _next_value_after_label(lines, [r"family name", r"nom de famille"])
    given_value, given_excerpt = _next_value_after_label(lines, [r"given name", r"prenom"])
    if family_value and given_value:
        family_value = " ".join(family_value.split())
        given_value = " ".join(given_value.split())
        person_name = f"{given_value.title()} {family_value.title()}"
        evidence["person_name"] = _evidence(person_name, "label_block_match", f"{given_excerpt}\n{family_excerpt}")
        return person_name, evidence

    header_name, header_excerpt = _header_name(lines)
    if header_name:
        evidence["person_name"] = _evidence(header_name, "header_match", header_excerpt, confidence="medium")
        return header_name, evidence

    return None, evidence


def _collect_numbered_lines(text: str, heading: str, stop_markers: tuple[str, ...]) -> list[str]:
    lowered_text = text.lower()
    start_index = lowered_text.find(heading.lower())
    if start_index == -1:
        return []

    section = text[start_index:].splitlines()[1:]
    results: list[str] = []
    for raw_line in section:
        line = raw_line.strip()
        if not line:
            if results:
                break
            continue
        if any(marker.lower() in line.lower() for marker in stop_markers):
            break
        if re.match(r"^\d+\.\s*", line):
            results.append(re.sub(r"^\d+\.\s*", "", line).strip())
            continue
        if results:
            results[-1] = f"{results[-1]} {line}".strip()
    return results


def _section_between(text: str, start_marker: str, end_marker: str) -> str:
    lowered = text.lower()
    start_index = lowered.find(start_marker.lower())
    if start_index == -1:
        return ""
    end_index = lowered.find(end_marker.lower(), start_index)
    if end_index == -1:
        return text[start_index:]
    return text[start_index:end_index]


def _extract_additional_info_values(text: str) -> dict[str, str]:
    section = _section_between(text, "ADDITIONAL INFORMATION", "Conditions:")
    if not section:
        return {}

    lines = [" ".join(line.strip().split()) for line in section.splitlines()]
    non_empty_lines = [line for line in lines if line]
    date_lines = [line for line in non_empty_lines if re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}", line)]
    uppercase_values = [
        line
        for line in non_empty_lines
        if re.fullmatch(r"[A-Z][A-Z /&'-]+", line)
        and "DATE" not in line
        and "CASE TYPE" not in line
        and "EMPLOYER" not in line
        and "OCCUPATION" not in line
        and "PASSPORT" not in line
        and "UNKNOWN" not in line
        and "IN FORCE" not in line
        and "LMIA" not in line
    ]

    result: dict[str, str] = {}
    if len(date_lines) >= 2:
        result["issue_date"] = date_lines[0]
        result["expiry_date"] = date_lines[1]
    if len(date_lines) >= 3:
        result["in_force_date"] = date_lines[-1]
    if uppercase_values:
        result["employer"] = uppercase_values[0]
    if len(uppercase_values) >= 2:
        result["occupation"] = uppercase_values[1]
    return result


def _extract_client_info_values(text: str) -> dict[str, str]:
    section = _section_between(text, "CLIENT INFORMATION", "ADDITIONAL INFORMATION")
    if not section:
        return {}

    lines = _normalized_lines(section)
    values = [
        line
        for line in lines
        if not _is_label_line(line)
        and not re.fullmatch(r"\(.*\)", line)
        and not re.fullmatch(r"[~.';:,\-\\/\s]+", line)
    ]

    compact_values: list[str] = []
    for line in values:
        normalized = " ".join(line.split())
        if not normalized:
            continue
        if normalized not in compact_values:
            compact_values.append(normalized)

    result: dict[str, str] = {}
    if len(compact_values) >= 3:
        result["family_name"] = compact_values[0]
        result["given_name"] = compact_values[1]
        result["dob"] = compact_values[2]
    if len(compact_values) >= 6:
        result["nationality"] = compact_values[5]
    elif len(compact_values) >= 5:
        result["nationality"] = compact_values[4]
    if len(compact_values) >= 7:
        result["travel_doc_type"] = compact_values[6]
    return result


def _extract_label_block_values(text: str) -> dict[str, tuple[str, str]]:
    lines = _normalized_lines(text)
    values: dict[str, tuple[str, str]] = {}
    label_map = {
        "dob": [r"date of birth", r"date de naissance"],
        "nationality": [r"country of citizenship", r"citoyen de"],
        "issue_date": [r"date issued", r"delivre le"],
        "expiry_date": [r"expiry date", r"date d'expiration", r"date <i'expiration"],
        "application_number": [r"application", r"demande"],
        "travel_doc_number": [r"travel doc"],
        "case_type": [r"case type", r"genre de cas"],
    }

    for key, patterns in label_map.items():
        value, excerpt = _next_value_after_label(lines, patterns)
        if not value:
            continue
        values[key] = (value, excerpt or value)

    return values


def _document_type(text: str, folded_text: str) -> tuple[str | None, str | None]:
    for source_text in (text, folded_text):
        for raw_line in source_text.splitlines():
            line = " ".join(raw_line.strip().split())
            if not line:
                continue
            if re.fullmatch(r"WORK PERMIT\s*/\s*PERMIS DE TRAVAIL", line, flags=re.IGNORECASE):
                return "work_permit", line
            if re.fullmatch(r"STUDY PERMIT(?:\s*/\s*PERMIS D['’]ETUDES)?", line, flags=re.IGNORECASE):
                return "study_permit", line
    return None, None


def _collect_generic_date_lines(text: str) -> dict[str, tuple[str, str]]:
    folded_text = _fold_text(text)
    results: dict[str, tuple[str, str]] = {}
    patterns = {
        "dob": [
            r"Date of Birth.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"Date de naissance.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
        ],
        "issue_date": [
            r"Date Issued.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"Delivre le.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"In Force From.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
        ],
        "expiry_date": [
            r"Expiry Date.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"Date d'expiration.*?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"MUST LEAVE CANADA BY\s+([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
            r"VALID UNTIL\s+([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})",
        ],
    }
    for key, key_patterns in patterns.items():
        value, excerpt = _extract_named_date(key_patterns, text, folded_text)
        if value:
            results[key] = (value, excerpt or value)
    return results


def parse_ircc_permit_text(text: str, filename: str) -> dict | None:
    compact_text = _compact_text(text)
    folded_text = _fold_text(compact_text)
    document_type, doc_excerpt = _document_type(compact_text, folded_text)
    if document_type is None:
        return None

    evidence: dict[str, dict] = {
        "document_type": _evidence(document_type, "label_match", doc_excerpt),
        "issuing_authority": _evidence("IRCC", "header_match", "Immigration, Refugees and Citizenship Canada"),
    }

    data: dict = {
        "document_type": document_type,
        "issuing_authority": "IRCC",
        "person_name": "",
        "dob": None,
        "nationality": None,
        "visa_type": None,
        "permit_type": "work permit" if document_type == "work_permit" else "study permit",
        "employer": None,
        "occupation": None,
        "issue_date": None,
        "expiry_date": None,
        "conditions": [],
        "restrictions": [],
        "reference_numbers": {},
        "deadlines": [],
        "raw_important_text": [],
        "field_evidence": evidence,
        "document_confidence": "high",
        "extraction_method": "label_parser",
        "raw_text": compact_text,
    }
    evidence["permit_type"] = _evidence(data["permit_type"], "label_match", doc_excerpt)

    person_name, name_evidence = _parse_name(compact_text, folded_text)
    if person_name:
        data["person_name"] = person_name
        evidence.update(name_evidence)

    client_info = _extract_client_info_values(compact_text)
    if not data["person_name"] and client_info.get("family_name") and client_info.get("given_name"):
        person_name = f"{client_info['given_name'].title()} {client_info['family_name'].title()}"
        data["person_name"] = person_name
        evidence["person_name"] = _evidence(person_name, "client_info_block_match", "CLIENT INFORMATION section", confidence="high")
    if not data["dob"] and client_info.get("dob"):
        normalized_dob = parse_loose_date(client_info["dob"]) or client_info["dob"].replace("/", "-")
        data["dob"] = normalized_dob
        evidence["dob"] = _evidence(normalized_dob, "client_info_block_match", "CLIENT INFORMATION section", confidence="high")
    if client_info.get("nationality") and (
        not data["nationality"] or _looks_like_label_artifact(str(data["nationality"]))
    ):
        data["nationality"] = client_info["nationality"]
        evidence["nationality"] = _evidence(client_info["nationality"], "client_info_block_match", "CLIENT INFORMATION section", confidence="high")

    field_patterns = {
        "dob": [r"Date of Birth/Date de naissance:\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})"],
        "nationality": [r"Country of Citizenship/Citoyen de:\s*([A-Z][A-Z ]+)", r"Country of Citizenship.*?:\s*([A-Z][A-Z ]+)"],
        "issue_date": [r"Date Issued/D[ée]livr[ée] le:\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})", r"Date Issued/Delivre le:\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})"],
        "expiry_date": [r"Expiry Date/Date d.expiration:\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})", r"Expiry Date/Date d.expiration\s*:?\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})"],
        "employer": [r"Employer/Employeur:\s*([^\n]+)"],
        "occupation": [r"Occupation/Profession:\s*([^\n]+)"],
        "application_number": [r"Application/Demande:\s*([A-Z0-9]+)"],
        "uci": [r"UCI/UC:\s*([0-9-]+)"],
        "travel_doc_number": [r"Travel Doc No\./N[°o] du document de voyage:\s*([A-Z0-9]+)"],
        "case_type": [r"Case Type/Genre de cas:\s*([A-Z0-9]+)"],
    }

    for field_name, patterns in field_patterns.items():
        value, excerpt = _search(patterns, compact_text, folded_text)
        if not value:
            continue
        cleaned = " ".join(value.split())
        if field_name in {"dob", "issue_date", "expiry_date"}:
            cleaned = parse_loose_date(cleaned) or cleaned.replace("/", "-")
        if field_name in {"application_number", "uci", "travel_doc_number", "case_type"}:
            data["reference_numbers"][field_name] = cleaned
        else:
            data[field_name] = cleaned
        evidence[field_name] = _evidence(cleaned, "label_match", excerpt)

    for field_name in ("person_name", "nationality", "visa_type"):
        if _looks_like_label_artifact(data.get(field_name)):
            data[field_name] = None if field_name != "person_name" else ""
            evidence.pop(field_name, None)

    for ref_key in ("travel_doc_number", "case_type"):
        ref_value = data["reference_numbers"].get(ref_key)
        if not isinstance(ref_value, str):
            continue
        cleaned_ref = ref_value.strip()
        if cleaned_ref.upper() == "PASSPORT" or not re.search(r"[A-Z0-9]{2,}", cleaned_ref):
            data["reference_numbers"].pop(ref_key, None)
            evidence.pop(ref_key, None)

    block_values = _extract_label_block_values(compact_text)
    for field_name, (value, excerpt) in block_values.items():
        if data.get(field_name):
            continue
        cleaned = " ".join(value.split())
        if field_name in {"dob", "issue_date", "expiry_date"}:
            cleaned = parse_loose_date(cleaned) or cleaned.replace("/", "-")
        if field_name in {"application_number", "uci", "travel_doc_number", "case_type"}:
            data["reference_numbers"][field_name] = cleaned
        else:
            data[field_name] = cleaned
        confidence = "high" if field_name in {"dob", "issue_date", "expiry_date", "nationality"} else "medium"
        evidence[field_name] = _evidence(cleaned, "label_block_match", excerpt, confidence=confidence)

    for field_name, (value, excerpt) in _collect_generic_date_lines(compact_text).items():
        if data.get(field_name):
            continue
        data[field_name] = value
        evidence[field_name] = _evidence(value, "ocr_pattern_match", excerpt, confidence="medium")

    additional_info = _extract_additional_info_values(compact_text)
    for field_name in ("issue_date", "expiry_date", "employer", "occupation"):
        value = additional_info.get(field_name)
        if not value:
            continue
        normalized = parse_loose_date(value) if field_name in {"issue_date", "expiry_date"} else value
        normalized = normalized or value
        data[field_name] = normalized
        evidence[field_name] = _evidence(normalized, "ocr_block_match", "ADDITIONAL INFORMATION section", confidence="high")

    if document_type == "study_permit" and data.get("expiry_date"):
        data["deadlines"] = [
            {
                "action": "Review study permit before expiry",
                "date": data["expiry_date"],
                "urgency": "future",
                "source_document": filename,
            }
        ]
        if additional_info.get("issue_date"):
            data["issue_date"] = parse_loose_date(additional_info["issue_date"]) or additional_info["issue_date"].replace("/", "-")
            evidence["issue_date"] = _evidence(data["issue_date"], "ocr_block_match", "ADDITIONAL INFORMATION section", confidence="high")

    conditions = _collect_numbered_lines(compact_text, "Conditions:", ("Remarks/Observations",))
    remarks, remarks_excerpt = _search([r"Remarks/Observations:\s*([\s\S]+)$"], compact_text, folded_text)
    if remarks:
        remarks_lines = [line.strip() for line in remarks.splitlines() if line.strip()]
        for line in remarks_lines[:3]:
            data["raw_important_text"].append(line)
            if "authorized" in line.lower() or "employment" in line.lower():
                conditions.append(line)

    if conditions:
        normalized_conditions: list[str] = []
        normalized_restrictions: list[str] = []
        for condition in conditions:
            normalized = " ".join(condition.split())
            if not normalized:
                continue
            if normalized not in normalized_conditions:
                normalized_conditions.append(normalized)
            if any(token in normalized.lower() for token in ("not valid", "must leave")) and normalized not in normalized_restrictions:
                normalized_restrictions.append(normalized)
        data["conditions"] = normalized_conditions
        data["restrictions"] = normalized_restrictions
        evidence["conditions"] = _evidence("; ".join(normalized_conditions[:3]), "label_match", "Conditions section")
    elif remarks_excerpt:
        evidence["conditions"] = _evidence("", "label_match", remarks_excerpt, confidence="medium")

    if data["expiry_date"] and not data["deadlines"]:
        data["deadlines"] = [
            {
                "action": f"Review {data['permit_type']} before expiry",
                "date": data["expiry_date"],
                "urgency": "future",
                "source_document": filename,
            }
        ]

    if not data["person_name"] or not data["expiry_date"]:
        data["document_confidence"] = "medium"

    return data
