from __future__ import annotations

import railtracks as rt

from shared.profile_normalizer import normalize_required_actions


def _default_steps_for_action(action: dict) -> list[dict]:
    title = action.get("title", "").lower()
    deadline = action.get("deadline")

    if "verify whether a newer permit or extension filing exists" in title:
        return [
            {
                "step_number": 1,
                "instruction": "Check for any newer permit, maintained-status filing, or IRCC approval that post-dates the uploaded document.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": "Use the upload only as evidence of what was provided, not proof that no newer status exists.",
            },
            {
                "step_number": 2,
                "instruction": "Gather the current permit, passport, recent IRCC correspondence, and any submission confirmations tied to renewal or restoration.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": None,
            },
            {
                "step_number": 3,
                "instruction": "If no newer approval or filing exists, review restoration or a new status strategy before relying on work, travel, or study plans.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": None,
            },
        ]

    if "extension" in title:
        return [
            {
                "step_number": 1,
                "instruction": "Review the current document and confirm the expiry date that drives this action.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": None,
            },
            {
                "step_number": 2,
                "instruction": "Gather supporting evidence such as enrollment, employment, passport validity, and any recent IRCC correspondence.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": None,
            },
            {
                "step_number": 3,
                "instruction": f"Prepare the application package before {deadline}." if deadline else "Prepare the application package before the relevant deadline.",
                "form_name": None,
                "form_number": None,
                "official_link": None,
                "fee": None,
                "processing_time": None,
                "tip": None,
            },
        ]

    return []


@rt.function_node
def generate_action_plan(profile: dict, knowledge_base: dict) -> dict:
    """Enrich required actions with IRCC knowledge base forms data."""
    enriched_actions = []
    for action in normalize_required_actions(profile.get("required_actions")):
        action_id = action.get("action_id", "")
        kb_entry = None
        for form_key, form_data in knowledge_base.get("forms", {}).items():
            if form_key in action_id or form_key in action.get("title", "").lower():
                kb_entry = form_data
                break

        if kb_entry:
            enriched_steps = []
            req_docs = kb_entry.get("required_documents", [])
            for i, doc in enumerate(req_docs, 1):
                enriched_steps.append(
                    {
                        "step_number": i,
                        "instruction": f"Gather: {doc}",
                        "form_name": None,
                        "form_number": None,
                        "official_link": None,
                        "fee": None,
                        "processing_time": None,
                        "tip": None,
                    }
                )
            enriched_steps.append(
                {
                    "step_number": len(req_docs) + 1,
                    "instruction": f"Complete {kb_entry.get('form_number', 'application form')}",
                    "form_name": None,
                    "form_number": kb_entry.get("form_number"),
                    "official_link": kb_entry.get("official_link"),
                    "fee": kb_entry.get("fee"),
                    "processing_time": kb_entry.get("processing_time"),
                    "tip": kb_entry.get("common_mistakes", [None])[0],
                }
            )
            action["steps"] = enriched_steps
        elif not action.get("steps"):
            action["steps"] = _default_steps_for_action(action)
        enriched_actions.append(action)

    profile["required_actions"] = normalize_required_actions(enriched_actions)
    return profile
