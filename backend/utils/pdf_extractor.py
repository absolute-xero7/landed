from __future__ import annotations

import fitz


def extract_text_from_pdf(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        pages = [page.get_text().strip() for page in doc]
    return "\n\n".join([page for page in pages if page])
