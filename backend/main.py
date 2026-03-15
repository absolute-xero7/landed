from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from agents.qa_agent import answer_question
from flows.landed_flow import KNOWLEDGE_BASE, run_session_pipeline
from models.schemas import UploadArtifact
from shared.profile_normalizer import normalize_profile
from shared.session_enrichment import build_session_enrichment, compute_session_diff, snapshot_session_state
from shared.translator import translate_profile

app = FastAPI(title="Landed")
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
MAX_FILES = int(os.getenv("MAX_FILES_PER_UPLOAD", "10"))

# In-memory session store only.
sessions: dict[str, dict] = {}


async def _process_session(session_id: str) -> None:
    state = sessions[session_id]
    queue: asyncio.Queue = state["queue"]

    async def emit_event(event: dict) -> None:
        await queue.put(event)

    try:
        result = await run_session_pipeline(state["files"], emit_event=emit_event)
        enrichment = build_session_enrichment(result.get("documents", []), result.get("profile"), KNOWLEDGE_BASE)
        state["documents"] = enrichment["documents"]
        state["profile"] = normalize_profile(enrichment["profile"])
        state["document_completeness"] = enrichment["document_completeness"]
        state["work_authorization"] = enrichment["work_authorization"]
        session_diff = compute_session_diff(
            state.pop("previous_snapshot", None),
            state["documents"],
            state["profile"],
            state.pop("pending_added_documents", []),
        )
        state["session_diff"] = session_diff
        await queue.put({"event": "complete", "data": json.dumps({"session_id": session_id, "session_diff": session_diff})})
    except Exception as exc:
        await queue.put({"event": "error", "data": json.dumps({"message": str(exc) or "Processing failed."})})
    finally:
        await queue.put(None)


def cleanup_sessions() -> None:
    """Remove sessions older than 2 hours."""
    cutoff = datetime.now() - timedelta(hours=2)
    expired = [sid for sid, sess in sessions.items() if sess.get("created_at", datetime.now()) < cutoff]
    for sid in expired:
        sessions.pop(sid, None)


async def _buffer_uploads(files: list[UploadFile]) -> list[UploadArtifact]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES} files allowed.")

    buffered: list[UploadArtifact] = []
    for file in files:
        ctype = file.content_type or "application/octet-stream"
        if ctype not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")
        payload = await file.read()
        if len(payload) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB: {file.filename}")
        buffered.append(
            UploadArtifact(
                filename=file.filename,
                mime_type=ctype,
                data_base64=base64.b64encode(payload).decode("utf-8"),
            )
        )
    return buffered


def _start_session_processing(session_id: str) -> None:
    sessions[session_id]["queue"] = asyncio.Queue()
    sessions[session_id]["task"] = asyncio.create_task(_process_session(session_id))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "name": "Landed API",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "upload": "/api/upload",
        "demo_documents": "/api/demo/{filename}",
    }


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    """Validate, parse, reason, and plan for uploaded docs. SSE stream via /api/stream/{session_id}."""
    cleanup_sessions()
    buffered = await _buffer_uploads(files)

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "documents": [],
        "profile": None,
        "document_completeness": None,
        "work_authorization": None,
        "session_diff": None,
        "created_at": datetime.now(),
        "files": buffered,
        "queue": asyncio.Queue(),
    }
    _start_session_processing(session_id)
    return {"session_id": session_id}


@app.post("/api/session/{session_id}/upload")
async def append_upload(session_id: str, files: list[UploadFile] = File(...)):
    """Append documents to an existing session and rerun processing on the combined set."""
    cleanup_sessions()
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    task = state.get("task")
    if task and not task.done():
        raise HTTPException(status_code=409, detail="This session is still processing.")

    buffered = await _buffer_uploads(files)
    if len(state.get("files", [])) + len(buffered) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES} files allowed per session.")

    state["previous_snapshot"] = snapshot_session_state(state)
    state["pending_added_documents"] = [item.filename for item in buffered]
    state["files"].extend(buffered)
    state["created_at"] = datetime.now()
    _start_session_processing(session_id)
    return {"session_id": session_id, "file_count": len(state["files"])}


@app.get("/api/stream/{session_id}")
async def stream(session_id: str):
    """SSE stream for upload pipeline progress."""
    if session_id not in sessions:
        async def error():
            yield {"event": "error", "data": json.dumps({"message": "Session not found"})}

        return EventSourceResponse(error())

    async def event_generator():
        queue: asyncio.Queue = sessions[session_id]["queue"]
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    return EventSourceResponse(event_generator())


@app.get("/api/session/{session_id}")
async def get_session(session_id: str, language: str = "English"):
    """Return full in-memory session payload once processing is complete."""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    profile = normalize_profile(state.get("profile"))
    if profile and language != "English":
        profile = translate_profile(profile, language)
    return {
        "profile": profile,
        "documents": state.get("documents", []),
        "document_completeness": state.get("document_completeness"),
        "work_authorization": state.get("work_authorization"),
    }


@app.post("/api/qa")
async def qa(session_id: str = Form(...), question: str = Form(...), language: str = Form("English")):
    """Answer grounded questions for a session."""
    state = sessions.get(session_id)
    if not state or not state.get("profile"):
        raise HTTPException(status_code=404, detail="Session not found or documents not yet processed.")
    answer = await asyncio.to_thread(
        answer_question,
        question,
        state["profile"],
        state["documents"],
        language,
        state.get("work_authorization"),
        state.get("document_completeness"),
    )
    return {"answer": answer}


@app.get("/api/demo/{filename}")
async def demo_doc(filename: str):
    path = f"demo/{filename}"
    if os.path.exists(path):
        return FileResponse(path, media_type="application/pdf")
    raise HTTPException(status_code=404, detail="Not found.")
