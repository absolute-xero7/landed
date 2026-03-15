from __future__ import annotations

from utils.llm_client import get_llm_client, has_llm_client


MODEL = "openai/gpt-oss-120b"


def translate(text: str, target_language: str) -> str:
    if target_language.lower() in {"en", "english"}:
        return text

    if not text.strip() or not has_llm_client():
        return text

    client = get_llm_client()
    msg = client.chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Translate the following immigration guidance text to {target_language}. "
                    "Keep all proper nouns, form numbers (IMM XXXX), official website URLs, and dates in their original form. "
                    "Translate only the explanatory text. Return only the translated text, no commentary.\n\n"
                    f"Text: {text}"
                ),
            }
        ],
    )
    return (msg.choices[0].message.content or "").strip()
