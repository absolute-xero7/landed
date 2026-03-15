from __future__ import annotations

import base64
import json
import pathlib
from inspect import isawaitable
from typing import Awaitable, Callable

import railtracks as rt

from agents.document_parser import parse_document
from agents.guidance_generator import generate_action_plan
from agents.situation_reasoner import synthesize_status
from models.schemas import UploadArtifact


KB_PATH = pathlib.Path(__file__).resolve().parents[1] / "knowledge" / "ircc_knowledge_base.json"
KNOWLEDGE_BASE = json.loads(KB_PATH.read_text()) if KB_PATH.exists() else {}


def _upload_priority(filename: str) -> tuple[int, str]:
    lowered = filename.lower()
    if "study" in lowered:
        return (0, lowered)
    if "work_permit" in lowered or "work permit" in lowered:
        return (1, lowered)
    if "trv" in lowered or "visa" in lowered:
        return (2, lowered)
    if "passport" in lowered:
        return (3, lowered)
    if "ircc" in lowered or "correspondence" in lowered:
        return (4, lowered)
    return (5, lowered)


async def _emit(event_type: str, payload: dict) -> None:
    try:
        callback = rt.context.get("emit_event")
    except KeyError:
        return

    result = callback({"event": event_type, "data": json.dumps(payload)})
    if isawaitable(result):
        await result


@rt.function_node
async def upload_pipeline(files: list[UploadArtifact]) -> dict:
    """Run the Landed upload pipeline: parse uploaded files, synthesize status, and generate an action plan."""
    parsed_docs: list[dict] = []

    for artifact in sorted(files, key=lambda item: _upload_priority(item.filename)):
        await _emit("parsing", {"filename": artifact.filename, "status": "started"})
        doc = await rt.call(
            parse_document,
            base64.b64decode(artifact.data_base64.encode("utf-8")),
            artifact.mime_type,
            artifact.filename,
        )
        parsed_docs.append(doc)
        await _emit(
            "parsing",
            {
                "filename": artifact.filename,
                "status": "complete",
                "document_type": doc.get("document_type"),
                "expiry_date": doc.get("expiry_date"),
                "deadlines_found": len(doc.get("deadlines", [])),
            },
        )

    await _emit("reasoning", {"status": "started"})
    profile = await rt.call(synthesize_status, parsed_docs)
    await _emit("reasoning", {"status": "complete", "urgency_level": profile.get("urgency_level")})

    await _emit("planning", {"status": "started"})
    profile = await rt.call(generate_action_plan, profile, KNOWLEDGE_BASE)
    await _emit("planning", {"status": "complete"})

    return {"documents": parsed_docs, "profile": profile}


landed_flow = rt.Flow(name="Landed", entry_point=upload_pipeline)


async def run_session_pipeline(
    files: list[UploadArtifact],
    emit_event: Callable[[dict], Awaitable[None] | None] | None = None,
) -> dict:
    """Invoke the Railtracks upload flow with optional SSE event emission."""
    flow = landed_flow.update_context({"emit_event": emit_event}) if emit_event is not None else landed_flow
    return await flow.ainvoke(files)
