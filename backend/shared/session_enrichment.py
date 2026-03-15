from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import re


RECOMMENDED_DOCS = {
    "passport": "Your passport expiry date is needed to check if it needs renewal before other applications.",
    "study_permit": "Required to determine your authorized activities and stay duration.",
    "trv": "Required to confirm your re-entry authorization.",
    "work_permit": "Required if you intend to work in Canada.",
}

CONFIDENCE_SCORES = {"low": 0.4, "medium": 0.8, "high": 0.95}


def _clean_condition_text(value: str) -> str:
    cleaned = re.split(
        r"\b(?:must leave canada|must\b|not valid for employment|cease working|employment practicum cannot)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = " ".join(cleaned.replace("~", " ").split())
    return cleaned.strip(" .,;:-")


def _study_work_policy(knowledge_base: dict) -> dict:
    policy = (knowledge_base.get("work_authorization") or {}).get("study_permit", {})
    return policy if isinstance(policy, dict) else {}


def _active_document_for_type(documents: list[dict], document_type: str) -> dict | None:
    dated: list[tuple[date, dict]] = []
    undated: list[dict] = []
    for document in documents:
        if document.get("document_type") != document_type:
            continue
        expiry_date = document.get("expiry_date")
        if isinstance(expiry_date, str):
            try:
                dated.append((date.fromisoformat(expiry_date), document))
                continue
            except ValueError:
                pass
        undated.append(document)
    if dated:
        dated.sort(key=lambda item: item[0], reverse=True)
        return dated[0][1]
    return undated[0] if undated else None


def _unique_strings(items: list[str]) -> list[str]:
    ordered: list[str] = []
    for item in items:
        cleaned = " ".join(item.split()).strip()
        if cleaned and cleaned not in ordered:
            ordered.append(cleaned)
    return ordered


def normalize_permit_type(value: str | None) -> str:
    if not value:
        return ""

    lowered = value.strip().lower()
    replacements = {
        "temporary resident visa": "trv",
        "study permit": "study_permit",
        "work permit": "work_permit",
        "permit extension": "permit_extension",
        "post-graduation work permit": "pgwp",
        "post graduation work permit": "pgwp",
        "electronic travel authorization": "eta",
        "eта": "eta",
    }
    for source, target in replacements.items():
        if source in lowered:
            return target

    token = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if token.startswith("work_permit"):
        return "work_permit"
    if token.startswith("study_permit"):
        return "study_permit"
    if token.startswith("permit_extension"):
        return "permit_extension"
    if token.startswith("pgwp"):
        return "pgwp"
    return token


def confidence_to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in CONFIDENCE_SCORES:
            return CONFIDENCE_SCORES[lowered]
        try:
            return float(lowered)
        except ValueError:
            return 0.0
    return 0.0


def detect_deadline_type(deadline: dict, profile: dict | None = None) -> str:
    action = str(deadline.get("action") or "").lower()
    source_document = str(deadline.get("source_document") or "").lower()
    combined = f"{action} {source_document}"

    if "trv" in combined or "temporary resident visa" in combined or "visitor visa" in combined:
        return "trv"
    if "pgwp" in combined or "post-graduation work permit" in combined:
        return "pgwp"
    if "study permit" in combined:
        return "study_permit"
    if "work permit" in combined:
        return "work_permit"
    if "extension" in combined or "renew" in combined:
        return "permit_extension"
    if profile:
        return normalize_permit_type(str(profile.get("permit_type") or ""))
    return ""


def calculate_apply_by(expiry_date: str, permit_type: str, knowledge_base: dict) -> dict:
    try:
        expiry = date.fromisoformat(expiry_date)
    except (TypeError, ValueError):
        return {
            "recommended_apply_by": None,
            "latest_apply_by": None,
            "estimated_completion": None,
            "days_until_recommended": None,
            "is_overdue": None,
            "processing_note": None,
            "processing_weeks_min": None,
            "processing_weeks_max": None,
        }

    timing = (knowledge_base.get("processing_times") or {}).get(normalize_permit_type(permit_type))
    if not isinstance(timing, dict):
        return {
            "recommended_apply_by": None,
            "latest_apply_by": None,
            "estimated_completion": None,
            "days_until_recommended": None,
            "is_overdue": None,
            "processing_note": None,
            "processing_weeks_min": None,
            "processing_weeks_max": None,
        }

    weeks_min = int(timing.get("weeks_min", 0))
    weeks_max = int(timing.get("weeks_max", 0))
    recommended_buffer_weeks = int(timing.get("recommended_buffer_weeks", weeks_max))
    today = date.today()

    recommended_apply_by = expiry - timedelta(weeks=recommended_buffer_weeks)
    latest_apply_by = expiry - timedelta(weeks=weeks_min)
    estimated_completion = today + timedelta(weeks=weeks_max)
    days_until_recommended = (recommended_apply_by - today).days

    return {
        "recommended_apply_by": recommended_apply_by.isoformat(),
        "latest_apply_by": latest_apply_by.isoformat(),
        "estimated_completion": estimated_completion.isoformat(),
        "days_until_recommended": days_until_recommended,
        "is_overdue": days_until_recommended < 0,
        "processing_note": (
            f"Processing takes {weeks_min}–{weeks_max} weeks. "
            f"Apply by {recommended_apply_by.isoformat()} to be safe."
        ),
        "processing_weeks_min": weeks_min,
        "processing_weeks_max": weeks_max,
    }


def calculate_implied_status(expiry_date: str, permit_type: str) -> dict:
    expiry = date.fromisoformat(expiry_date)
    today = date.today()
    days_remaining = (expiry - today).days
    normalized = normalize_permit_type(permit_type)
    eligible = normalized not in ["trv", "passport", "eta", "eта"]

    return {
        "eligible": eligible,
        "must_apply_before": expiry_date,
        "days_to_deadline": days_remaining,
        "explanation": (
            f"To maintain implied status, submit your renewal application before {expiry_date}. "
            f"If you apply before this date, you may legally remain in Canada under the same conditions "
            f"while IRCC processes your application — even after your permit expires."
            if eligible
            else f"Implied status does not apply to {normalized or permit_type}. "
            f"You must have a valid {normalized or permit_type} to re-enter Canada."
        ),
        "warning": (
            "Implied status does NOT allow re-entry to Canada if you travel abroad. "
            "Ensure your TRV is also valid before any international travel."
            if eligible
            else None
        ),
    }


def check_document_completeness(documents: list[dict]) -> dict:
    uploaded_types = {d.get("document_type") for d in documents if d.get("document_type")}
    missing = []
    for doc_type, reason in RECOMMENDED_DOCS.items():
        if doc_type not in uploaded_types:
            missing.append({"type": doc_type, "reason": reason})
    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "uploaded_count": len(documents),
        "uploaded_types": sorted(uploaded_types),
    }


def calculate_work_authorization(documents: list[dict], profile: dict, knowledge_base: dict | None = None) -> dict | None:
    knowledge_base = knowledge_base or {}
    relevant_lines: list[str] = []
    source_document: str | None = None
    on_campus = False
    off_campus_hours: int | None = None
    full_time_breaks = False
    coop_authorized = False
    no_work = False
    work_permit_present = False
    profile_permit_type = normalize_permit_type(str(profile.get("permit_type") or ""))

    for document in documents:
        if document.get("document_type") == "work_permit":
            work_permit_present = True
        for condition in document.get("conditions", []):
            if not isinstance(condition, str):
                continue
            cleaned = _clean_condition_text(condition)
            lowered = cleaned.lower()
            if "work" not in lowered and "campus" not in lowered and "co-op" not in lowered and "coop" not in lowered and "practicum" not in lowered:
                continue
            if cleaned and cleaned not in relevant_lines:
                relevant_lines.append(cleaned)
            source_document = source_document or document.get("filename")

            if any(token in lowered for token in ("not authorized to work", "may not work", "must not work", "no employment authorized")):
                no_work = True
            if "on campus" in lowered or "on or off campus" in lowered:
                on_campus = True
            hours_match = re.search(r"(\d{1,2})\s*hours?\s*(?:/|per)?\s*week", lowered)
            if hours_match:
                off_campus_hours = int(hours_match.group(1))
            if (
                re.search(r"full\W*time.*(?:break|reak)", lowered)
                or re.search(r"ful\W*time.*(?:break|reak|gular)", lowered)
                or ("full" in lowered and "time during" in lowered and any(token in lowered for token in ("r186(v)", "gular", "scheduled")))
                or ("ful" in lowered and "time during" in lowered and any(token in lowered for token in ("r186(v)", "gular", "scheduled")))
            ):
                full_time_breaks = True
            if "co-op" in lowered or "coop" in lowered or "practicum" in lowered or "integral part of studies" in lowered:
                coop_authorized = True

    if not relevant_lines and not work_permit_present:
        return None

    policy = _study_work_policy(knowledge_base)
    active_study_permit = _active_document_for_type(documents, "study_permit")
    study_policy_hours = None
    if profile_permit_type == "study_permit" and active_study_permit:
        study_policy_hours = policy.get("off_campus_hours_per_week")
        if isinstance(study_policy_hours, int):
            off_campus_hours = max(off_campus_hours or 0, study_policy_hours)
        source_document = active_study_permit.get("filename") or source_document
        if any("on campus" in line.lower() or "on or off campus" in line.lower() for line in relevant_lines):
            on_campus = True
        if any(
            "r186(v)" in line.lower() or "scheduled breaks" in line.lower() or "regular breaks" in line.lower()
            for line in relevant_lines
        ):
            full_time_breaks = True

    authorized = False if no_work else bool(
        on_campus or off_campus_hours is not None or full_time_breaks or coop_authorized or work_permit_present
    )
    off_campus_hours_per_month = off_campus_hours * 4 if off_campus_hours is not None else None

    if no_work:
        plain_english = "The uploaded documents indicate that you are not authorized to work under the current conditions."
    else:
        parts: list[str] = []
        if off_campus_hours is not None:
            parts.append(
                f"You may work up to {off_campus_hours} hours per week off-campus during academic sessions "
                f"({off_campus_hours_per_month} hours/month)."
            )
        if full_time_breaks:
            parts.append("You may also work full-time during scheduled breaks and holidays.")
        if on_campus:
            parts.append("On-campus work appears authorized with no specific hour cap stated.")
        if coop_authorized:
            parts.append("Co-op or practicum work appears authorized.")
        if work_permit_present and not parts:
            parts.append("You appear authorized to work in Canada under the conditions listed on the uploaded work permit.")
        plain_english = " ".join(parts).strip() or "Work authorization details were not clear enough to summarize."

    key_points: list[str] = []
    if profile_permit_type == "study_permit" and active_study_permit:
        key_points.append("Study at the designated learning institution listed on the active study permit.")
        if off_campus_hours is not None:
            key_points.append(f"May work up to {off_campus_hours} hours per week off campus during regular academic sessions if otherwise eligible.")
        if on_campus:
            key_points.append("May work on campus if otherwise eligible.")
        if full_time_breaks:
            key_points.append("May work full-time during scheduled breaks if otherwise eligible.")
        if coop_authorized:
            key_points.append("Co-op or practicum work appears authorized where required by the program.")
    else:
        if work_permit_present:
            key_points.append("Work appears authorized under the conditions listed on the active work permit.")
        if off_campus_hours is not None:
            key_points.append(f"Off-campus work appears limited to {off_campus_hours} hours per week.")
        if on_campus:
            key_points.append("On-campus work appears authorized.")
        if full_time_breaks:
            key_points.append("Full-time work during scheduled breaks appears authorized.")
        if coop_authorized:
            key_points.append("Co-op or practicum work appears authorized.")

    return {
        "authorized": authorized,
        "on_campus": on_campus,
        "off_campus_hours_per_week": off_campus_hours,
        "off_campus_hours_per_month": off_campus_hours_per_month,
        "full_time_during_breaks": full_time_breaks,
        "coop_authorized": coop_authorized,
        "source_document": source_document,
        "plain_english": plain_english,
        "conditions_raw": relevant_lines,
        "key_points": _unique_strings(key_points),
        "policy_note": policy.get("policy_note") if profile_permit_type == "study_permit" else None,
        "policy_effective_date": policy.get("effective_date") if profile_permit_type == "study_permit" else None,
        "policy_source_url": policy.get("source_url") if profile_permit_type == "study_permit" else None,
    }


def low_confidence_fields(document: dict) -> list[str]:
    evidence = document.get("field_evidence", {})
    if not isinstance(evidence, dict):
        return []
    flagged = [
        field_name
        for field_name, field_evidence in evidence.items()
        if isinstance(field_evidence, dict) and confidence_to_float(field_evidence.get("confidence")) < 0.75
    ]
    return sorted(dict.fromkeys(flagged))


def enrich_documents(documents: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for document in documents:
        item = deepcopy(document)
        item["low_confidence_fields"] = low_confidence_fields(document)
        enriched.append(item)
    return enriched


def _infer_deadline_source(deadline: dict, documents: list[dict]) -> str:
    existing = deadline.get("source_document")
    if isinstance(existing, str) and existing.strip():
        return existing

    deadline_type = detect_deadline_type(deadline)
    for document in documents:
        if document.get("document_type") == deadline_type:
            filename = document.get("filename")
            if isinstance(filename, str) and filename:
                return filename

    for document in documents:
        if document.get("expiry_date") == deadline.get("date"):
            filename = document.get("filename")
            if isinstance(filename, str) and filename:
                return filename

    return "uploaded documents"


def _active_status_document(documents: list[dict]) -> dict | None:
    candidates: list[tuple[date, dict]] = []
    for document in documents:
        if document.get("document_type") not in {"study_permit", "work_permit"}:
            continue
        expiry_date = document.get("expiry_date")
        if not isinstance(expiry_date, str):
            continue
        try:
            parsed = date.fromisoformat(expiry_date)
        except ValueError:
            continue
        if parsed >= date.today():
            candidates.append((parsed, document))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _normalize_deadline_action(action: object) -> str:
    if not isinstance(action, str):
        return ""
    lowered = action.strip().lower()
    replacements = {
        "review study permit before expiry": "Renew study permit before expiry",
        "review work permit before expiry": "Renew work permit before expiry",
        "study permit expires": "Renew study permit before expiry",
        "work permit expires": "Renew work permit before expiry",
    }
    return replacements.get(lowered, action.strip())


def _deadline_is_superseded(deadline: dict, documents: list[dict], active_document: dict | None) -> bool:
    if not active_document:
        return False

    action = str(deadline.get("action") or "").strip().lower()
    source_document = str(deadline.get("source_document") or "")
    if not source_document or source_document == active_document.get("filename"):
        return False

    try:
        deadline_date = date.fromisoformat(str(deadline.get("date") or ""))
        active_expiry = date.fromisoformat(str(active_document.get("expiry_date") or ""))
    except ValueError:
        return False

    if deadline_date >= active_expiry:
        return False

    source_doc = next((document for document in documents if document.get("filename") == source_document), None)
    source_type = source_doc.get("document_type") if isinstance(source_doc, dict) else None
    if source_type not in {"study_permit", "work_permit"}:
        return False

    if "leave canada" in action:
        return True

    return action in {
        "review study permit before expiry",
        "review work permit before expiry",
        "renew study permit before expiry",
        "renew work permit before expiry",
        "study permit expires",
        "work permit expires",
    }


def enrich_profile(profile: dict | None, documents: list[dict], knowledge_base: dict) -> dict | None:
    if not isinstance(profile, dict):
        return profile

    enriched = deepcopy(profile)
    active_document = _active_status_document(documents)
    deadlines = []
    for deadline in enriched.get("all_deadlines", []):
        item = deepcopy(deadline)
        item["source_document"] = _infer_deadline_source(item, documents)
        item["action"] = _normalize_deadline_action(item.get("action"))
        if _deadline_is_superseded(item, documents, active_document):
            continue
        deadline_type = detect_deadline_type(item, enriched)
        if item.get("date"):
            item.update(calculate_apply_by(item["date"], deadline_type, knowledge_base))
        consequences = (knowledge_base.get("consequences") or {}).get(deadline_type, {})
        item["consequence"] = consequences.get("missed")
        item["consequence_action"] = consequences.get("action")
        deadlines.append(item)
    enriched["all_deadlines"] = deadlines

    actions = []
    for action in enriched.get("required_actions", []):
        item = deepcopy(action)
        title = str(item.get("title") or "").strip()
        if title:
            item["title"] = _normalize_deadline_action(title)
        normalized_type = normalize_permit_type(str(enriched.get("permit_type") or ""))
        title = str(item.get("title") or "").lower()
        if "trv" in title or "temporary resident visa" in title or "visitor visa" in title:
            normalized_type = "trv"
        elif "pgwp" in title:
            normalized_type = "pgwp"
        elif "study permit" in title:
            normalized_type = "study_permit"
        elif "work permit" in title:
            normalized_type = "work_permit"
        elif "extension" in title:
            normalized_type = "permit_extension"

        deadline = item.get("deadline")
        if isinstance(deadline, str) and deadline:
            try:
                item["implied_status"] = calculate_implied_status(deadline, normalized_type or str(enriched.get("permit_type") or ""))
            except ValueError:
                item["implied_status"] = None
        actions.append(item)
    enriched["required_actions"] = actions
    return enriched


def build_session_enrichment(documents: list[dict], profile: dict | None, knowledge_base: dict) -> dict:
    enriched_documents = enrich_documents(documents)
    enriched_profile = enrich_profile(profile, enriched_documents, knowledge_base)
    work_authorization = calculate_work_authorization(enriched_documents, enriched_profile or {}, knowledge_base)
    if enriched_profile and isinstance(work_authorization, dict):
        if work_authorization.get("key_points"):
            enriched_profile["authorized_activities"] = work_authorization["key_points"]
    return {
        "documents": enriched_documents,
        "profile": enriched_profile,
        "document_completeness": check_document_completeness(enriched_documents),
        "work_authorization": work_authorization,
    }


def snapshot_session_state(state: dict) -> dict:
    profile = state.get("profile") or {}
    previous_deadlines = profile.get("all_deadlines", []) if isinstance(profile, dict) else []
    return {
        "previous_document_count": len(state.get("documents", [])),
        "previous_document_types": sorted(
            {
                document.get("document_type")
                for document in state.get("documents", [])
                if isinstance(document, dict) and document.get("document_type")
            }
        ),
        "previous_deadlines": deepcopy(previous_deadlines),
        "previous_urgency_level": profile.get("urgency_level") if isinstance(profile, dict) else None,
        "previous_current_status": profile.get("current_status") if isinstance(profile, dict) else None,
    }


def compute_session_diff(previous_snapshot: dict | None, current_documents: list[dict], current_profile: dict | None, added_documents: list[str]) -> dict | None:
    if not previous_snapshot:
        return None

    previous_deadlines = {
        (item.get("action"), item.get("date"))
        for item in previous_snapshot.get("previous_deadlines", [])
        if isinstance(item, dict)
    }
    current_deadlines = [
        item
        for item in (current_profile or {}).get("all_deadlines", [])
        if isinstance(item, dict) and (item.get("action"), item.get("date")) not in previous_deadlines
    ]

    status_changed = (
        previous_snapshot.get("previous_urgency_level") != (current_profile or {}).get("urgency_level")
        or previous_snapshot.get("previous_current_status") != (current_profile or {}).get("current_status")
    )

    summary_parts = [f"Added {len(added_documents)} document{'s' if len(added_documents) != 1 else ''}."]
    if current_deadlines:
        first = current_deadlines[0]
        summary_parts.append(f"New deadline detected: {first.get('action')} by {first.get('date')}.")
    elif status_changed:
        summary_parts.append("Your status summary was updated.")
    else:
        summary_parts.append("Session analysis refreshed with the new documents.")

    return {
        "previous_document_count": previous_snapshot.get("previous_document_count", 0),
        "previous_document_types": previous_snapshot.get("previous_document_types", []),
        "previous_deadlines": previous_snapshot.get("previous_deadlines", []),
        "added_documents": added_documents,
        "removed_documents": [],
        "new_deadlines_found": current_deadlines,
        "status_changed": status_changed,
        "summary": " ".join(summary_parts),
    }
