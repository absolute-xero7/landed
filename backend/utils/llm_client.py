from __future__ import annotations

from openai import OpenAI

from config import get_settings


HF_OPENAI_BASE_URL = "https://router.huggingface.co/v1"


def has_llm_client() -> bool:
    return bool(get_settings().openai_api_key)


def get_llm_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key, base_url=HF_OPENAI_BASE_URL)