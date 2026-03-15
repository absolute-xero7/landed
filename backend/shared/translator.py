from __future__ import annotations

import json

import railtracks as rt

from shared.llm_client import call_gpt
from shared.profile_normalizer import normalize_profile


@rt.function_node
def translate_text(text: str, target_language: str) -> str:
    """Translate text while preserving dates, form numbers, URLs, and key proper nouns."""
    if target_language == "English":
        return text
    try:
        return call_gpt(
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"""Translate to {target_language}.
Keep dates, form numbers (e.g. IMM 5257), URLs, and proper nouns (IRCC, CRA, PGWP, SIN, OHIP) in English.
Return only the translated text, no preamble.

Text: {text}"""
                    ),
                }
            ],
            max_tokens=800,
        )
    except RuntimeError:
        return text


def translate_profile(profile: dict, target_language: str) -> dict:
    """Translate user-facing profile fields while preserving structured identifiers and dates."""
    if target_language == "English":
        return normalize_profile(profile) or profile

    try:
        response = call_gpt(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate only the human-readable strings in this immigration profile JSON. "
                        "Keep keys unchanged. Preserve dates, urgency values, action_id, form numbers, URLs, and official identifiers exactly. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Translate this JSON to {target_language}:\n\n{json.dumps(profile, ensure_ascii=False)}",
                },
            ],
            max_tokens=2500,
            json_mode=True,
        )
        translated = json.loads(response)
        if isinstance(translated, dict):
            return normalize_profile(translated) or translated
    except (RuntimeError, json.JSONDecodeError, TypeError):
        pass

    return normalize_profile(profile) or profile
