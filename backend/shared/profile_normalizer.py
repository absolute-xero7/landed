from __future__ import annotations

from copy import deepcopy


def normalize_action_step(step: object, index: int) -> dict | None:
    if isinstance(step, str):
        instruction = step.strip()
        if not instruction:
            return None
        return {
            "step_number": index,
            "instruction": instruction,
            "form_name": None,
            "form_number": None,
            "official_link": None,
            "fee": None,
            "processing_time": None,
            "tip": None,
        }

    if not isinstance(step, dict):
        return None

    instruction = str(step.get("instruction") or "").strip()
    if not instruction:
        return None

    raw_step_number = step.get("step_number")
    step_number = raw_step_number if isinstance(raw_step_number, int) and raw_step_number > 0 else index

    def optional_string(value: object) -> str | None:
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return None

    return {
        "step_number": step_number,
        "instruction": instruction,
        "form_name": optional_string(step.get("form_name")),
        "form_number": optional_string(step.get("form_number")),
        "official_link": optional_string(step.get("official_link")),
        "fee": optional_string(step.get("fee")),
        "processing_time": optional_string(step.get("processing_time")),
        "tip": optional_string(step.get("tip")),
    }


def normalize_required_actions(actions: object) -> list[dict]:
    if not isinstance(actions, list):
        return []

    normalized: list[dict] = []
    for action in actions:
        if not isinstance(action, dict):
            continue

        title = str(action.get("title") or "").strip()
        if not title:
            continue

        raw_steps = action.get("steps")
        step_items = raw_steps if isinstance(raw_steps, list) else []
        steps = [
            normalized_step
            for index, step in enumerate(step_items, start=1)
            if (normalized_step := normalize_action_step(step, index)) is not None
        ]

        normalized.append(
            {
                "action_id": str(action.get("action_id") or title.lower().replace(" ", "_")),
                "title": title,
                "urgency": str(action.get("urgency") or "upcoming"),
                "deadline": action.get("deadline") if isinstance(action.get("deadline"), str) else None,
                "steps": steps,
                "implied_status": action.get("implied_status") if isinstance(action.get("implied_status"), dict) else None,
            }
        )

    return normalized


def normalize_profile(profile: dict | None) -> dict | None:
    if not isinstance(profile, dict):
        return profile

    normalized = deepcopy(profile)
    normalized["required_actions"] = normalize_required_actions(profile.get("required_actions"))
    return normalized
