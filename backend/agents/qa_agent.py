from __future__ import annotations

import re

import railtracks as rt

from shared.fallbacks import build_grounded_qa_answer, build_qa_fallback, document_label
from shared.llm_client import LLMUnavailableError, call_gpt
from shared.translator import translate_text


def _sanitize_answer_text(answer: str) -> str:
    cleaned = answer.replace("**", "")
    cleaned = re.sub(r"\|[-\s|:]+\|", " ", cleaned)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    return cleaned.strip()


@rt.function_node
def answer_question(
    question: str,
    profile: dict,
    documents: list[dict],
    language: str = "English",
    work_authorization: dict | None = None,
    document_completeness: dict | None = None,
) -> str:
    """Answer grounded in uploaded documents and profile data."""
    grounded_answer = build_grounded_qa_answer(question, profile, documents, work_authorization, document_completeness)
    if grounded_answer is not None:
        answer = grounded_answer
        if language != "English":
            answer = translate_text(answer, language)
        return _sanitize_answer_text(answer)

    source_manifest = "\n".join(
        f"- {document_label(document, index)} => filename={document.get('filename', 'unknown')}, type={document.get('document_type')}"
        for index, document in enumerate(documents, start=1)
    )
    normalized_documents = "\n\n".join(
        f"Document: {d.get('filename', 'unknown')}\n"
        f"Type: {d.get('document_type')}\n"
        f"Person name: {d.get('person_name') or 'unverified'}\n"
        f"Expiry date: {d.get('expiry_date') or 'unknown'}\n"
        f"Issue date: {d.get('issue_date') or 'unknown'}\n"
        f"Reference numbers: {d.get('reference_numbers') or {}}\n"
        f"Low confidence fields: {', '.join(d.get('low_confidence_fields', [])) or 'none'}"
        for d in documents
    )

    try:
        answer = call_gpt(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Canadian immigration assistant answering questions about a specific person's documents. "
                        "Always cite sources using exactly this format: 'Source: study permit (document 1).' "
                        "Use only the provided source labels, avoid hallucination, and flag when an answer is general information. "
                        "Only answer from the normalized facts provided below; do not quote OCR text directly. "
                        "If the upload does not support the answer, say that you cannot verify it from the uploaded documents. "
                        "Answer in plain text only. Do not use markdown tables, bullets, or bold formatting. Keep it to 2-4 sentences."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""Immigration profile:
{profile}

Work authorization summary:
{work_authorization}

Document completeness:
{document_completeness}

Source labels:
{source_manifest}

Normalized document facts:
{normalized_documents}

Question: {question}""",
                },
            ],
            max_tokens=600,
        )
    except LLMUnavailableError:
        answer = build_qa_fallback(question, profile, documents, work_authorization, document_completeness)

    if "Source:" not in answer and documents:
        answer = f"{answer.rstrip()} Source: {document_label(documents[0], 1)}."

    if language != "English":
        answer = translate_text(answer, language)

    return _sanitize_answer_text(answer)
