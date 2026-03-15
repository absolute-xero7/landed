from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz

from shared.llm_client import LLMUnavailableError, call_gpt


OCR_TEXT_PROMPT = """Transcribe this immigration document exactly.
Return plain text only.
Preserve labels, numbers, dates, and line breaks as faithfully as possible.
Do not summarize. Do not infer missing words. If text is unreadable, omit it."""
REFUSAL_HINTS = (
    "i'm sorry",
    "i’m sorry",
    "i can't",
    "i can’t",
    "can't view or extract text",
    "cannot view or extract text",
    "provide the document's contents as plain text",
    "provide the document’s contents as plain text",
)


@dataclass
class OCRResult:
    text: str
    method: str
    confidence: str


SWIFT_OCR_SCRIPT = Path(__file__).with_name("macos_ocr.swift")
SWIFT_MODULE_CACHE_DIR = Path(tempfile.gettempdir()) / "landed-swift-module-cache"


def extract_native_pdf_text(file_bytes: bytes) -> str:
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            pages = [page.get_text("text").strip() for page in doc]
    except Exception:
        return ""
    return "\n\n".join(page for page in pages if page)


def render_pdf_pages(file_bytes: bytes, max_pages: int = 3) -> list[bytes]:
    images: list[bytes] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page_index in range(min(len(doc), max_pages)):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                images.append(pix.tobytes("png"))
    except Exception:
        return []
    return images


def _run_macos_ocr(image_bytes_list: list[bytes], suffix: str = ".png") -> str:
    if not image_bytes_list or not SWIFT_OCR_SCRIPT.exists():
        return ""

    temp_dir = Path(tempfile.mkdtemp(prefix="landed-ocr-"))
    image_paths: list[str] = []
    module_cache_dir = SWIFT_MODULE_CACHE_DIR
    module_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        for index, image_bytes in enumerate(image_bytes_list):
            image_path = temp_dir / f"page-{index}{suffix}"
            image_path.write_bytes(image_bytes)
            image_paths.append(str(image_path))

        result = subprocess.run(
            ["/usr/bin/swift", "-module-cache-path", str(module_cache_dir), str(SWIFT_OCR_SCRIPT), *image_paths],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""

        parsed = json.loads(result.stdout)
        if not isinstance(parsed, list):
            return ""

        texts: list[str] = []
        for item in parsed:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                texts.append(item["text"].strip())
        return "\n\n".join(texts)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return ""
    finally:
        for file_path in temp_dir.glob("*"):
            try:
                if file_path.is_file():
                    file_path.unlink()
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def _macos_vision_ocr(file_bytes: bytes, mime_type: str) -> OCRResult | None:
    if mime_type == "application/pdf":
        images = render_pdf_pages(file_bytes)
        text = _run_macos_ocr(images)
        if text.strip():
            return OCRResult(text=text, method="macos_vision_ocr", confidence="high")
        return None

    if mime_type not in {"image/png", "image/jpeg", "image/jpg"}:
        return None

    suffix = ".png" if mime_type == "image/png" else ".jpg"
    text = _run_macos_ocr([file_bytes], suffix=suffix)
    if text.strip():
        return OCRResult(text=text, method="macos_vision_ocr", confidence="high")
    return None


def _vision_content_from_images(images: list[bytes], filename: str) -> list[dict]:
    parts: list[dict] = []
    for image_bytes in images:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"},
            }
        )
    parts.append({"type": "text", "text": f"Filename: {filename}\n{OCR_TEXT_PROMPT}"})
    return parts


def _vision_content_from_file(file_bytes: bytes, mime_type: str, filename: str) -> list[dict]:
    if mime_type == "application/pdf":
        return _vision_content_from_images(render_pdf_pages(file_bytes), filename)

    return [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode()}"}},
        {"type": "text", "text": f"Filename: {filename}\n{OCR_TEXT_PROMPT}"},
    ]


def _vision_ocr(file_bytes: bytes, mime_type: str, filename: str) -> OCRResult:
    response = call_gpt(messages=[{"role": "user", "content": _vision_content_from_file(file_bytes, mime_type, filename)}], max_tokens=2500)
    return OCRResult(text=response.strip(), method="vision_ocr", confidence="medium")


def _looks_like_ocr_refusal(text: str) -> bool:
    lowered = text.strip().lower()
    return any(hint in lowered for hint in REFUSAL_HINTS)


def extract_document_text(file_bytes: bytes, mime_type: str, filename: str) -> OCRResult:
    if mime_type == "application/pdf":
        text = extract_native_pdf_text(file_bytes)
        if len(text.strip()) > 120:
            return OCRResult(text=text, method="native_pdf_text", confidence="high")

    macos_result = _macos_vision_ocr(file_bytes, mime_type)
    if macos_result is not None:
        return macos_result

    try:
        result = _vision_ocr(file_bytes, mime_type, filename)
        if _looks_like_ocr_refusal(result.text):
            return OCRResult(text="", method="vision_ocr_refused", confidence="low")
        return result
    except LLMUnavailableError:
        if mime_type == "application/pdf":
            text = extract_native_pdf_text(file_bytes)
            if text.strip():
                return OCRResult(text=text, method="native_pdf_text", confidence="medium")
        return OCRResult(text="", method="unavailable", confidence="low")
