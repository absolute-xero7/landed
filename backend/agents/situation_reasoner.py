from __future__ import annotations

import json
from datetime import date

import railtracks as rt

from shared.fallbacks import CONFIDENCE_ORDER, build_profile_fallback
from shared.llm_client import LLMUnavailableError, call_gpt


def _documents_are_reliable(documents: list[dict]) -> bool:
    if not documents:
        return False

    for document in documents:
        evidence = document.get("field_evidence", {})
        if not isinstance(evidence, dict):
            return False
        for field in ("document_type", "person_name"):
            field_evidence = evidence.get(field, {})
            confidence = str(field_evidence.get("confidence", "low")).lower()
            if CONFIDENCE_ORDER.get(confidence, 0) < CONFIDENCE_ORDER["medium"]:
                return False
    return True


@rt.function_node
def synthesize_status(documents: list[dict]) -> dict:
    """Cross-document reasoning to synthesize immigration status."""
    fallback_profile = build_profile_fallback(documents)
    if not _documents_are_reliable(documents):
        return fallback_profile

    try:
        response = call_gpt(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Canadian immigration expert. Synthesize immigration status from parsed documents. Return JSON only.",
                },
                {
                    "role": "user",
                    "content": f"""Given these parsed immigration documents, synthesize the person's complete immigration status.

Documents: {json.dumps(documents, indent=2)}
Today's date: {date.today().isoformat()}

Return ONLY valid JSON with no markdown:
{{
  "current_status": "plain English 1-2 sentence description",
  "permit_type": "primary permit type they hold",
  "authorized_activities": ["list of what they are authorized to do"],
  "expiry_date": "YYYY-MM-DD of most imminent expiry",
  "days_until_expiry": integer,
  "urgency_level": "critical (< 30 days) | urgent (30-60 days) | normal (> 60 days)",
  "all_deadlines": [merged deduplicated deadlines from all documents],
  "required_actions": [{{"action_id": "unique_id", "title": "Action title", "urgency": "urgent|upcoming|future", "deadline": "YYYY-MM-DD or null", "steps": []}}],
  "risks": ["list of identified risks or conflicts across documents"]
}}""",
                },
            ],
            max_tokens=2000,
            json_mode=True,
        )

        profile = json.loads(response)
        for key in ("all_deadlines", "required_actions", "risks"):
            if not profile.get(key):
                profile[key] = fallback_profile.get(key, [])
        for key in ("current_status", "permit_type", "expiry_date"):
            if not profile.get(key):
                profile[key] = fallback_profile.get(key)
        if profile.get("days_until_expiry") is None:
            profile["days_until_expiry"] = fallback_profile.get("days_until_expiry", 0)
        if not profile.get("urgency_level"):
            profile["urgency_level"] = fallback_profile.get("urgency_level", "normal")
        if not profile.get("authorized_activities"):
            profile["authorized_activities"] = fallback_profile.get("authorized_activities", [])
        return profile
    except (LLMUnavailableError, json.JSONDecodeError, TypeError):
        return fallback_profile
