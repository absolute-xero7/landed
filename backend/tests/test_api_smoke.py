import sys
import json
from pathlib import Path
from importlib import reload
from types import SimpleNamespace

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _demo_file(*candidates: str) -> Path:
    demo_dir = BACKEND_DIR / "demo"
    for candidate in candidates:
        path = demo_dir / candidate
        if path.exists():
            return path
    raise FileNotFoundError(f"None of the demo files exist: {candidates}")


def _make_client() -> tuple[TestClient, object]:
    import main

    reload(main)
    return TestClient(main.app), main


def test_healthcheck():
    client, _ = _make_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_metadata():
    client, _ = _make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Landed API"
    assert response.json()["docs"] == "/docs"


def test_document_upload_stream_session_and_qa_flow():
    client, main = _make_client()

    async def fake_run_session_pipeline(files, emit_event=None):
        assert files
        document = {
            "document_id": "doc-1",
            "filename": files[0].filename,
            "document_type": "study_permit",
            "issuing_authority": "IRCC",
            "person_name": "Alex Chen",
            "dob": None,
            "nationality": "India",
            "visa_type": None,
            "permit_type": "study permit",
            "employer": None,
            "occupation": None,
            "issue_date": None,
            "expiry_date": "2026-08-15",
            "conditions": ["Must remain enrolled"],
            "restrictions": [],
            "reference_numbers": {},
            "deadlines": [],
            "raw_important_text": ["Permit valid until 2026-08-15"],
            "extraction_method": "native_pdf_text",
            "document_confidence": "high",
            "field_evidence": {},
            "raw_text": "Permit valid until 2026-08-15",
        }
        profile = {
            "current_status": "Valid study permit holder.",
            "permit_type": "study permit",
            "authorized_activities": ["Study full-time"],
            "expiry_date": "2026-08-15",
            "days_until_expiry": 365,
            "urgency_level": "normal",
            "all_deadlines": [],
            "required_actions": [
                {
                    "action_id": "extend-study-permit",
                    "title": "Prepare extension package",
                    "urgency": "upcoming",
                    "deadline": "2026-06-01",
                    "steps": [
                        {
                            "step_number": 1,
                            "instruction": "Collect proof of enrollment",
                            "form_name": None,
                            "form_number": None,
                            "official_link": None,
                            "fee": None,
                            "processing_time": None,
                            "tip": None,
                        }
                    ],
                }
            ],
            "risks": [],
        }

        if emit_event is not None:
            await emit_event({"event": "parsing", "data": json.dumps({"filename": files[0].filename, "status": "started"})})
            await emit_event(
                {
                    "event": "parsing",
                    "data": json.dumps({"filename": files[0].filename, "status": "complete", "document_type": "study_permit"}),
                }
            )
            await emit_event({"event": "reasoning", "data": json.dumps({"status": "started"})})
            await emit_event({"event": "reasoning", "data": json.dumps({"status": "complete", "urgency_level": "normal"})})
            await emit_event({"event": "planning", "data": json.dumps({"status": "started"})})
            await emit_event({"event": "planning", "data": json.dumps({"status": "complete"})})

        return {"documents": [document], "profile": profile}

    def fake_answer_question(
        question: str,
        profile: dict,
        documents: list[dict],
        language: str,
        work_authorization=None,
        document_completeness=None,
    ):
        assert question
        assert profile["permit_type"] == "study permit"
        assert documents[0]["document_type"] == "study_permit"
        return "Your study permit appears valid until 2026-08-15."

    main.run_session_pipeline = fake_run_session_pipeline
    main.answer_question = fake_answer_question
    main.translate_profile = lambda profile, language: {**profile, "current_status": f"{language} translation"}

    upload = client.post(
        "/api/upload",
        files={"files": ("study_permit.pdf", b"%PDF-1.4\nFake PDF", "application/pdf")},
    )
    assert upload.status_code == 200
    session_id = upload.json()["session_id"]

    seen_events = set()
    with client.stream("GET", f"/api/stream/{session_id}") as stream:
        assert stream.status_code == 200
        pending_event = None
        for line in stream.iter_lines():
            if line.startswith("event:"):
                pending_event = line.split(":", 1)[1].strip()
            if line.startswith("data:") and pending_event:
                payload = json.loads(line.split(":", 1)[1].strip())
                seen_events.add(pending_event)
                if pending_event == "complete":
                    assert payload["session_id"] == session_id
                    break
                pending_event = None

    assert "parsing" in seen_events
    assert "reasoning" in seen_events
    assert "planning" in seen_events
    assert "complete" in seen_events

    session_response = client.get(f"/api/session/{session_id}")
    assert session_response.status_code == 200
    session_payload = session_response.json()

    assert session_payload["profile"] is not None
    assert session_payload["documents"]
    assert session_payload["documents"][0]["document_type"] == "study_permit"
    assert "document_completeness" in session_payload
    assert "work_authorization" in session_payload
    assert "low_confidence_fields" in session_payload["documents"][0]

    localized = client.get(f"/api/session/{session_id}?language=Hindi")
    assert localized.status_code == 200
    assert localized.json()["profile"]["current_status"] == "Hindi translation"

    qa = client.post(
        "/api/qa",
        data={"session_id": session_id, "question": "When does my permit expire?", "language": "English"},
    )
    assert qa.status_code == 200
    assert "study permit" in qa.json()["answer"].lower()


def test_session_append_upload_reprocesses_same_session():
    client, main = _make_client()
    run_calls: list[list[str]] = []

    async def fake_run_session_pipeline(files, emit_event=None):
        run_calls.append([file.filename for file in files])
        profile = {
            "current_status": "Documents processed.",
            "permit_type": "study permit",
            "authorized_activities": ["Study full-time"],
            "expiry_date": "2026-08-15",
            "days_until_expiry": 365,
            "urgency_level": "normal",
            "all_deadlines": [],
            "required_actions": [],
            "risks": [],
        }
        documents = [
            {
                "document_id": f"doc-{index}",
                "filename": file.filename,
                "document_type": "other",
                "issuing_authority": "IRCC",
                "person_name": "Alex Chen",
                "dob": None,
                "nationality": None,
                "visa_type": None,
                "permit_type": None,
                "employer": None,
                "occupation": None,
                "issue_date": None,
                "expiry_date": None,
                "conditions": [],
                "restrictions": [],
                "reference_numbers": {},
                "deadlines": [],
                "raw_important_text": [],
                "extraction_method": "test",
                "document_confidence": "high",
                "field_evidence": {},
                "raw_text": "",
            }
            for index, file in enumerate(files, start=1)
        ]
        return {"documents": documents, "profile": profile}

    main.run_session_pipeline = fake_run_session_pipeline

    first_upload = client.post(
        "/api/upload",
        files={"files": ("study_permit.pdf", b"%PDF-1.4\nFake PDF", "application/pdf")},
    )
    assert first_upload.status_code == 200
    session_id = first_upload.json()["session_id"]

    append_upload = client.post(
        f"/api/session/{session_id}/upload",
        files={"files": ("passport.pdf", b"%PDF-1.4\nFake PDF", "application/pdf")},
    )
    assert append_upload.status_code == 200
    assert append_upload.json()["session_id"] == session_id
    assert run_calls[0] == ["study_permit.pdf"]
    assert run_calls[1] == ["study_permit.pdf", "passport.pdf"]

    session_payload = client.get(f"/api/session/{session_id}").json()
    assert session_payload["document_completeness"]["uploaded_count"] == 2


def test_chat_translation_endpoint_translates_existing_messages():
    client, main = _make_client()

    translated_calls: list[tuple[str, str]] = []

    def fake_translate_text(text: str, language: str) -> str:
        translated_calls.append((text, language))
        return f"{language}:{text}"

    main.translate_text = fake_translate_text

    response = client.post(
        "/api/chat/translate",
        json={
            "language": "Hindi",
            "messages": [
                {"role": "user", "content": "Can I work?"},
                {"role": "assistant", "content": "You may work up to 24 hours per week."},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["messages"] == [
        "Hindi:Can I work?",
        "Hindi:You may work up to 24 hours per week.",
    ]
    assert translated_calls == [
        ("Can I work?", "Hindi"),
        ("You may work up to 24 hours per week.", "Hindi"),
    ]


def test_session_response_normalizes_string_steps():
    client, main = _make_client()

    async def fake_run_session_pipeline(files, emit_event=None):
        return {
            "documents": [],
            "profile": {
                "current_status": "Status needs review.",
                "permit_type": "work permit",
                "authorized_activities": [],
                "expiry_date": "2025-09-30",
                "days_until_expiry": -10,
                "urgency_level": "critical",
                "all_deadlines": [],
                "required_actions": [
                    {
                        "action_id": "restore_status",
                        "title": "Apply for restoration",
                        "urgency": "urgent",
                        "deadline": "2025-09-30",
                        "steps": [
                            "Collect the current permit and passport.",
                            "Prepare the restoration filing.",
                        ],
                    }
                ],
                "risks": [],
            },
        }

    main.run_session_pipeline = fake_run_session_pipeline

    upload = client.post(
        "/api/upload",
        files={"files": ("work_permit.pdf", b"%PDF-1.4\nFake PDF", "application/pdf")},
    )
    assert upload.status_code == 200
    session_id = upload.json()["session_id"]

    payload = client.get(f"/api/session/{session_id}").json()
    steps = payload["profile"]["required_actions"][0]["steps"]
    assert steps[0]["instruction"] == "Collect the current permit and passport."
    assert steps[0]["step_number"] == 1
    assert steps[1]["instruction"] == "Prepare the restoration filing."


def test_session_enrichment_adds_processing_and_consequence_fields():
    from shared.session_enrichment import build_session_enrichment

    knowledge_base = json.loads((BACKEND_DIR / "knowledge" / "ircc_knowledge_base.json").read_text())
    documents = [
        {
            "document_id": "doc-1",
            "filename": "study_permit.pdf",
            "document_type": "study_permit",
            "issuing_authority": "IRCC",
            "person_name": "Alex Chen",
            "dob": None,
            "nationality": "India",
            "visa_type": None,
            "permit_type": "study permit",
            "employer": None,
            "occupation": None,
            "issue_date": None,
            "expiry_date": "2026-08-15",
            "conditions": [
                "May work 24 hours per week off campus during academic sessions.",
                "May work on campus.",
                "May work full-time during scheduled breaks.",
            ],
            "restrictions": [],
            "reference_numbers": {},
            "deadlines": [],
            "raw_important_text": [],
            "extraction_method": "test",
            "document_confidence": "high",
            "field_evidence": {"expiry_date": {"confidence": "low", "source": "test", "value": "2026-08-15", "excerpt": "Expiry"}},
            "raw_text": "",
        }
    ]
    profile = {
        "current_status": "Valid study permit holder.",
        "permit_type": "study permit",
        "authorized_activities": ["Study full-time"],
        "expiry_date": "2026-08-15",
        "days_until_expiry": 150,
        "urgency_level": "normal",
        "all_deadlines": [
            {
                "action": "Study permit expires",
                "date": "2026-08-15",
                "urgency": "future",
                "days_remaining": 150,
                "source_document": "study_permit.pdf",
            }
        ],
        "required_actions": [
            {
                "action_id": "permit_extension",
                "title": "Prepare study permit extension",
                "urgency": "future",
                "deadline": "2026-08-15",
                "steps": [],
            }
        ],
        "risks": [],
    }

    enriched = build_session_enrichment(documents, profile, knowledge_base)

    deadline = enriched["profile"]["all_deadlines"][0]
    assert deadline["recommended_apply_by"]
    assert deadline["consequence"]
    assert deadline["processing_weeks_min"] == 4
    assert deadline["processing_weeks_max"] == 12
    assert enriched["profile"]["required_actions"][0]["implied_status"]["eligible"] is True
    assert enriched["documents"][0]["low_confidence_fields"] == ["expiry_date"]
    assert enriched["document_completeness"]["missing"]
    assert enriched["work_authorization"]["authorized"] is True
    assert enriched["work_authorization"]["off_campus_hours_per_week"] == 24
    assert enriched["work_authorization"]["policy_effective_date"] == "2024-11-08"
    assert any("24 hours per week" in item for item in enriched["profile"]["authorized_activities"])


def test_compressed_study_permit_extracts_name_and_expiry_when_present():
    import agents.document_parser as document_parser

    study_path = _demo_file("Study Permit_compressed.pdf")
    document = document_parser.parse_document(study_path.read_bytes(), "application/pdf", study_path.name)

    assert document["document_type"] == "study_permit"
    assert document["person_name"] == "Prahlad Ranjit"
    assert document["expiry_date"] == "2026-09-30"
    assert document["issue_date"] == "2025-03-06"
    assert document["visa_type"] is None


def test_profile_fallback_prefers_active_study_permit_over_expired_work_permit():
    from shared.fallbacks import build_profile_fallback

    documents = [
        {
            "filename": "Work Permit_compressed.pdf",
            "document_type": "work_permit",
            "person_name": "Prahlad Ranjit",
            "permit_type": "work permit",
            "expiry_date": "2025-09-30",
            "conditions": [
                "MUST LEAVE CANADA BY 2025/09/30",
                "NOT VALID FOR EMPLOYMENT IN BUSINESSES RELATED TO THE SEX TRADE SUCH AS STRIP CLUBS, MASSAGE PARLOURS OR ESCORT SERVICES.",
            ],
            "field_evidence": {
                "document_type": {"confidence": "high"},
                "person_name": {"confidence": "high"},
                "expiry_date": {"confidence": "high"},
            },
            "deadlines": [
                {
                    "action": "Review work permit before expiry",
                    "date": "2025-09-30",
                    "urgency": "urgent",
                    "days_remaining": -1,
                    "source_document": "Work Permit_compressed.pdf",
                }
            ],
        },
        {
            "filename": "Study Permit_compressed.pdf",
            "document_type": "study_permit",
            "person_name": "Prahlad Ranjit",
            "permit_type": "study permit",
            "expiry_date": "2026-09-30",
            "conditions": [
                "MAY ACCEPT EMPLOYMENT ON OR OFF CAMPUS IF MEETING ELIGIBILITY CRITERIA AS PER R186(F), (V) OR (W).",
                "MAY WORK 20 HOURS/WEEK OFF CAMPUS OR FULL TIME DURING REGULAR BREAKS IF R186(V) CONDITIONS ARE MET.",
                "MUST LEAVE CANADA BY 2026/09/30",
            ],
            "field_evidence": {
                "document_type": {"confidence": "high"},
                "person_name": {"confidence": "high"},
                "expiry_date": {"confidence": "high"},
            },
            "deadlines": [
                {
                    "action": "Review study permit before expiry",
                    "date": "2026-09-30",
                    "urgency": "future",
                    "days_remaining": 199,
                    "source_document": "Study Permit_compressed.pdf",
                }
            ],
        },
    ]

    profile = build_profile_fallback(documents)

    assert profile["permit_type"] == "study permit"
    assert profile["expiry_date"] == "2026-09-30"
    assert profile["days_until_expiry"] >= 0
    assert "study permit" in profile["current_status"].lower()
    assert "prahlad ranjit" in profile["current_status"].lower()
    assert all("must leave canada by 2025/09/30" not in item.lower() for item in profile["authorized_activities"])
    assert any("20 hours/week" in item.lower() or "24 hours per week" in item.lower() for item in profile["authorized_activities"])
    assert not profile["risks"]


def test_work_authorization_ignores_sector_restriction_and_detects_breaks():
    from shared.session_enrichment import calculate_work_authorization

    documents = [
        {
            "filename": "Study Permit_compressed.pdf",
            "document_type": "study_permit",
            "conditions": [
                "MAY WORK 20 HOURS/WEEK OFF CAMPUS OR FUL~ TIME DURING ~~GULARJ3REAKS IF R186(V) CONDITIONS ARE MET,",
                "MAY ACCEPT EMPLOYMENT ON OR OFF CAMPUS IF MEETING ELIGIBILITY CRITERIA AS PER R186(F), (V) OR (W).",
            ],
        },
        {
            "filename": "Work Permit_compressed.pdf",
            "document_type": "work_permit",
            "conditions": [
                "NOT VALID FOR EMPLOYMENT IN BUSINESSES RELATED TO THE SEX TRADE SUCH AS STRIP CLUBS, MASSAGE PARLOURS OR ESCORT SERVICES."
            ],
        },
    ]

    knowledge_base = json.loads((BACKEND_DIR / "knowledge" / "ircc_knowledge_base.json").read_text())
    payload = calculate_work_authorization(documents, {"permit_type": "study permit"}, knowledge_base)

    assert payload is not None
    assert payload["authorized"] is True
    assert payload["off_campus_hours_per_week"] == 24
    assert payload["full_time_during_breaks"] is True
    assert payload["on_campus"] is True
    assert "not authorized to work" not in payload["plain_english"].lower()
    assert any("24 hours per week" in item for item in payload["key_points"])


def test_session_enrichment_filters_superseded_work_permit_deadline_and_renames_review():
    from shared.session_enrichment import build_session_enrichment

    knowledge_base = json.loads((BACKEND_DIR / "knowledge" / "ircc_knowledge_base.json").read_text())
    documents = [
        {
            "document_id": "doc-work",
            "filename": "Work Permit.pdf",
            "document_type": "work_permit",
            "issuing_authority": "IRCC",
            "person_name": "Prahlad Ranjit",
            "dob": None,
            "nationality": None,
            "visa_type": None,
            "permit_type": "work permit",
            "employer": None,
            "occupation": None,
            "issue_date": "2023-03-14",
            "expiry_date": "2025-09-30",
            "conditions": [],
            "restrictions": ["MUST LEAVE CANADA BY 2025/09/30"],
            "reference_numbers": {},
            "deadlines": [
                {
                    "action": "Leave Canada",
                    "date": "2025-09-30",
                    "urgency": "urgent",
                    "days_remaining": -1,
                    "source_document": "Work Permit.pdf",
                }
            ],
            "raw_important_text": [],
            "extraction_method": "test",
            "document_confidence": "high",
            "field_evidence": {
                "expiry_date": {"confidence": "high", "source": "test", "value": "2025-09-30", "excerpt": "Expiry"},
                "document_type": {"confidence": "high", "source": "test", "value": "work_permit", "excerpt": "Work permit"},
            },
            "raw_text": "",
        },
        {
            "document_id": "doc-study",
            "filename": "Study Permit.pdf",
            "document_type": "study_permit",
            "issuing_authority": "IRCC",
            "person_name": "Prahlad Ranjit",
            "dob": None,
            "nationality": None,
            "visa_type": None,
            "permit_type": "study permit",
            "employer": None,
            "occupation": None,
            "issue_date": "2025-03-06",
            "expiry_date": "2026-09-30",
            "conditions": [],
            "restrictions": [],
            "reference_numbers": {},
            "deadlines": [
                {
                    "action": "Review study permit before expiry",
                    "date": "2026-09-30",
                    "urgency": "future",
                    "days_remaining": 199,
                    "source_document": "Study Permit.pdf",
                }
            ],
            "raw_important_text": [],
            "extraction_method": "test",
            "document_confidence": "high",
            "field_evidence": {
                "expiry_date": {"confidence": "high", "source": "test", "value": "2026-09-30", "excerpt": "Expiry"},
                "document_type": {"confidence": "high", "source": "test", "value": "study_permit", "excerpt": "Study permit"},
            },
            "raw_text": "",
        },
    ]
    profile = {
        "current_status": "Prahlad Ranjit's uploaded study permit shows an expiry date of 2026-09-30.",
        "permit_type": "study permit",
        "authorized_activities": [],
        "expiry_date": "2026-09-30",
        "days_until_expiry": 199,
        "urgency_level": "normal",
        "all_deadlines": [
            {
                "action": "Leave Canada",
                "date": "2025-09-30",
                "urgency": "urgent",
                "days_remaining": -1,
                "source_document": "Work Permit.pdf",
            },
            {
                "action": "Review study permit before expiry",
                "date": "2026-09-30",
                "urgency": "future",
                "days_remaining": 199,
                "source_document": "Study Permit.pdf",
            },
        ],
        "required_actions": [
            {
                "action_id": "deadline_follow_up",
                "title": "Review study permit before expiry",
                "urgency": "future",
                "deadline": "2026-09-30",
                "steps": [],
            }
        ],
        "risks": [],
    }

    enriched = build_session_enrichment(documents, profile, knowledge_base)

    assert len(enriched["profile"]["all_deadlines"]) == 1
    assert enriched["profile"]["all_deadlines"][0]["action"] == "Renew study permit before expiry"
    assert enriched["profile"]["required_actions"][0]["title"] == "Renew study permit before expiry"


def test_expired_trv_pdf_extracts_expiry_and_name():
    import agents.document_parser as document_parser

    trv_path = _demo_file("TRV (expired).pdf")
    document = document_parser.parse_document(trv_path.read_bytes(), "application/pdf", trv_path.name)

    assert document["document_type"] == "trv"
    assert document["person_name"] == "Prahlad Ranjit"
    assert document["expiry_date"] == "2025-09-03"
    assert document["issue_date"] is None


def test_profile_fallback_warns_when_trv_is_expired_but_permit_remains_valid():
    from shared.fallbacks import build_profile_fallback

    documents = [
        {
            "filename": "Study Permit.pdf",
            "document_type": "study_permit",
            "person_name": "Prahlad Ranjit",
            "permit_type": "study permit",
            "expiry_date": "2026-09-30",
            "conditions": [],
            "field_evidence": {
                "document_type": {"confidence": "high"},
                "person_name": {"confidence": "high"},
                "expiry_date": {"confidence": "high"},
            },
            "deadlines": [
                {
                    "action": "Renew study permit before expiry",
                    "date": "2026-09-30",
                    "urgency": "future",
                    "days_remaining": 199,
                    "source_document": "Study Permit.pdf",
                }
            ],
        },
        {
            "filename": "TRV (expired).pdf",
            "document_type": "trv",
            "person_name": "Prahlad Ranjit",
            "visa_type": "temporary resident visa",
            "expiry_date": "2025-09-03",
            "conditions": [],
            "field_evidence": {
                "document_type": {"confidence": "high"},
                "person_name": {"confidence": "high"},
                "expiry_date": {"confidence": "medium"},
            },
            "deadlines": [
                {
                    "action": "Temporary resident visa expires",
                    "date": "2025-09-03",
                    "urgency": "urgent",
                    "days_remaining": -193,
                    "source_document": "TRV (expired).pdf",
                }
            ],
        },
    ]

    profile = build_profile_fallback(documents)

    assert profile["permit_type"] == "study permit"
    assert profile["expiry_date"] == "2026-09-30"
    assert any("trv appears expired" in risk.lower() for risk in profile["risks"])
    assert any(action["action_id"] == "trv_renewal" for action in profile["required_actions"])


def test_trv_required_action_does_not_get_implied_status():
    from shared.session_enrichment import build_session_enrichment

    knowledge_base = json.loads((BACKEND_DIR / "knowledge" / "ircc_knowledge_base.json").read_text())
    documents = []
    profile = {
        "current_status": "TRV renewal needed.",
        "permit_type": "study permit",
        "authorized_activities": [],
        "expiry_date": "2026-09-30",
        "days_until_expiry": 199,
        "urgency_level": "normal",
        "all_deadlines": [],
        "required_actions": [
            {
                "action_id": "trv_renewal",
                "title": "Renew temporary resident visa",
                "urgency": "urgent",
                "deadline": "2025-09-03",
                "steps": [],
            }
        ],
        "risks": [],
    }

    enriched = build_session_enrichment(documents, profile, knowledge_base)

    assert enriched["profile"]["required_actions"][0]["implied_status"]["eligible"] is False


def test_fallback_mode_without_llm_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    import shared.llm_client as llm_client
    import agents.document_parser as document_parser
    import agents.guidance_generator as guidance_generator
    import agents.qa_agent as qa_agent
    import agents.situation_reasoner as situation_reasoner

    reload(llm_client)
    reload(document_parser)
    reload(situation_reasoner)
    reload(guidance_generator)
    reload(qa_agent)

    study_path = _demo_file("study_permit_sample.pdf", "Study Permit_compressed.pdf")
    study_permit = document_parser.parse_document(
        study_path.read_bytes(),
        "application/pdf",
        study_path.name,
    )
    trv = {
        "document_id": "doc-trv",
        "filename": "trv_letter_sample.pdf",
        "document_type": "trv",
        "issuing_authority": "IRCC",
        "person_name": "Prahlad Ranjit",
        "dob": None,
        "nationality": "India",
        "visa_type": "temporary resident visa",
        "permit_type": None,
        "employer": None,
        "occupation": None,
        "issue_date": "2025-01-01",
        "expiry_date": "2026-04-03",
        "conditions": [],
        "restrictions": [],
        "reference_numbers": {},
        "deadlines": [],
        "raw_important_text": [],
        "extraction_method": "test",
        "document_confidence": "high",
        "field_evidence": {
            "document_type": {"value": "trv", "confidence": "high", "source": "test", "excerpt": "TRV"},
            "person_name": {"value": "Prahlad Ranjit", "confidence": "high", "source": "test", "excerpt": "Prahlad Ranjit"},
            "expiry_date": {"value": "2026-04-03", "confidence": "high", "source": "test", "excerpt": "2026-04-03"},
        },
        "raw_text": "",
        "low_confidence_fields": [],
    }
    correspondence = {
        "document_id": "doc-ircc",
        "filename": "ircc_correspondence_sample.pdf",
        "document_type": "ircc_letter",
        "issuing_authority": "IRCC",
        "person_name": "Prahlad Ranjit",
        "dob": None,
        "nationality": "India",
        "visa_type": None,
        "permit_type": None,
        "employer": None,
        "occupation": None,
        "issue_date": None,
        "expiry_date": None,
        "conditions": [],
        "restrictions": [],
        "reference_numbers": {},
        "deadlines": [
            {
                "action": "Submit requested documents",
                "date": "2026-02-01",
                "urgency": "upcoming",
                "days_remaining": 30,
                "source_document": "ircc_correspondence_sample.pdf",
            }
        ],
        "raw_important_text": [],
        "extraction_method": "test",
        "document_confidence": "high",
        "field_evidence": {
            "document_type": {"value": "ircc_letter", "confidence": "high", "source": "test", "excerpt": "IRCC"},
            "person_name": {"value": "Prahlad Ranjit", "confidence": "high", "source": "test", "excerpt": "Prahlad Ranjit"},
        },
        "raw_text": "",
        "low_confidence_fields": [],
    }

    documents = [study_permit, trv, correspondence]
    profile = situation_reasoner.synthesize_status(documents)
    profile = guidance_generator.generate_action_plan(profile, json.loads((BACKEND_DIR / "knowledge" / "ircc_knowledge_base.json").read_text()))
    answer = qa_agent.answer_question("When does my TRV expire?", profile, documents, "French")

    assert study_permit["document_type"] == "study_permit"
    assert trv["document_type"] == "trv"
    assert correspondence["document_type"] == "ircc_letter"
    assert profile["required_actions"]
    assert profile["required_actions"][0]["steps"]
    assert "2026-04-03" in answer

    work_answer = qa_agent.answer_question("Can this person work?", profile, documents, "English")
    assert "study permit (document 1)" in work_answer


def test_qa_uses_normalized_work_authorization_for_study_permit_questions():
    import agents.qa_agent as qa_agent

    documents = [
        {
            "document_id": "doc-study",
            "filename": "Study Permit_compressed.pdf",
            "document_type": "study_permit",
            "issuing_authority": "IRCC",
            "person_name": "Prahlad Ranjit",
            "dob": None,
            "nationality": None,
            "visa_type": None,
            "permit_type": "study permit",
            "employer": None,
            "occupation": None,
            "issue_date": "2025-03-06",
            "expiry_date": "2026-09-30",
            "conditions": [
                "MAY WORK 20 HOURS/WEEK OFF CAMPUS OR FUL~ TIME DURING ~~GULARJ3REAKS IF R186(V) CONDITIONS ARE MET,"
            ],
            "restrictions": [],
            "reference_numbers": {},
            "deadlines": [],
            "raw_important_text": [],
            "extraction_method": "test",
            "document_confidence": "high",
            "field_evidence": {
                "document_type": {"value": "study_permit", "confidence": "high", "source": "test", "excerpt": "study permit"},
                "person_name": {"value": "Prahlad Ranjit", "confidence": "high", "source": "test", "excerpt": "Prahlad Ranjit"},
            },
            "raw_text": "",
            "low_confidence_fields": [],
        }
    ]
    profile = {
        "current_status": "Prahlad Ranjit's uploaded study permit shows an expiry date of 2026-09-30.",
        "permit_type": "study permit",
        "authorized_activities": [
            "May work up to 24 hours per week off campus during regular academic sessions if otherwise eligible.",
            "May work on campus if otherwise eligible.",
            "May work full-time during scheduled breaks if otherwise eligible.",
        ],
        "expiry_date": "2026-09-30",
        "days_until_expiry": 199,
        "urgency_level": "normal",
        "all_deadlines": [],
        "required_actions": [],
        "risks": [],
    }
    work_authorization = {
        "authorized": True,
        "on_campus": True,
        "off_campus_hours_per_week": 24,
        "off_campus_hours_per_month": 96,
        "full_time_during_breaks": True,
        "coop_authorized": False,
        "source_document": "Study Permit_compressed.pdf",
        "plain_english": "You may work up to 24 hours per week off-campus during academic sessions (96 hours/month). You may also work full-time during scheduled breaks and holidays. On-campus work appears authorized with no specific hour cap stated.",
        "conditions_raw": [],
    }

    hours_answer = qa_agent.answer_question(
        "How long can I work while studying?",
        profile,
        documents,
        "English",
        work_authorization,
    )
    on_campus_answer = qa_agent.answer_question(
        "What about on campus jobs?",
        profile,
        documents,
        "English",
        work_authorization,
    )

    assert "24 hours per week" in hours_answer
    assert "study permit (document 1)" in hours_answer
    assert "gularj3reaks" not in hours_answer.lower()
    assert "on-campus work appears authorized" in on_campus_answer.lower()
    assert "study permit (document 1)" in on_campus_answer


def test_qa_answers_travel_implied_status_and_missing_docs_from_normalized_context():
    import agents.qa_agent as qa_agent

    documents = [
        {
            "document_id": "doc-study",
            "filename": "Study Permit_compressed.pdf",
            "document_type": "study_permit",
            "person_name": "Prahlad Ranjit",
            "expiry_date": "2026-09-30",
            "conditions": [],
            "raw_important_text": [],
        }
    ]
    profile = {
        "current_status": "Prahlad Ranjit's uploaded study permit shows an expiry date of 2026-09-30.",
        "permit_type": "study permit",
        "authorized_activities": [],
        "expiry_date": "2026-09-30",
        "days_until_expiry": 199,
        "urgency_level": "normal",
        "all_deadlines": [
            {
                "action": "Review study permit before expiry",
                "date": "2026-09-30",
                "urgency": "future",
                "days_remaining": 199,
                "source_document": "Study Permit_compressed.pdf",
                "consequence": "You lose legal status in Canada and are required to leave or restore status immediately.",
                "consequence_action": "Contact IRCC immediately and do not leave Canada voluntarily without guidance.",
            }
        ],
        "required_actions": [
            {
                "action_id": "deadline_follow_up",
                "title": "Review study permit before expiry",
                "urgency": "future",
                "deadline": "2026-09-30",
                "steps": [],
                "implied_status": {
                    "eligible": True,
                    "must_apply_before": "2026-09-30",
                    "days_to_deadline": 199,
                    "explanation": "To maintain implied status, submit your renewal application before 2026-09-30.",
                    "warning": "Implied status does not allow re-entry to Canada if you travel abroad.",
                },
            }
        ],
        "risks": [],
    }
    completeness = {
        "complete": False,
        "missing": [{"type": "trv", "reason": "Required to confirm your re-entry authorization."}],
        "uploaded_count": 1,
        "uploaded_types": ["study_permit"],
    }

    travel_answer = qa_agent.answer_question(
        "Can I travel and come back to Canada?",
        profile,
        documents,
        "English",
        None,
        completeness,
    )
    implied_answer = qa_agent.answer_question(
        "Do I have implied status if I apply before expiry?",
        profile,
        documents,
        "English",
        None,
        completeness,
    )
    missing_answer = qa_agent.answer_question(
        "What documents are missing?",
        profile,
        documents,
        "English",
        None,
        completeness,
    )

    assert "cannot confirm re-entry authorization" in travel_answer.lower()
    assert "study permit (document 1)" in travel_answer
    assert "maintain implied status" in implied_answer.lower()
    assert "trv" in missing_answer.lower()


def test_qa_sanitizes_markdown_table_noise(monkeypatch):
    import agents.qa_agent as qa_agent

    noisy = (
        "On-campus work is permitted. **Key points** | Requirement | Meaning |\n"
        "|---|---|\n"
        "| Valid study permit | Yes |\n"
        "Source: study permit (document 1)."
    )

    monkeypatch.setattr(qa_agent, "call_gpt", lambda *args, **kwargs: noisy)

    answer = qa_agent.answer_question(
        "What about on campus jobs?",
        {"current_status": "Status", "permit_type": "study permit", "authorized_activities": [], "expiry_date": "2026-09-30", "days_until_expiry": 199, "urgency_level": "normal", "all_deadlines": [], "required_actions": [], "risks": []},
        [{"filename": "Study Permit.pdf", "document_type": "study_permit", "conditions": [], "raw_important_text": []}],
        "English",
        None,
    )

    assert "**" not in answer
    assert "|---|" not in answer


def test_parse_document_coerces_nullable_required_string_fields(monkeypatch):
    import agents.document_parser as document_parser

    fake_response = json.dumps(
        {
            "document_type": "work_permit",
            "issuing_authority": None,
            "person_name": None,
            "dob": None,
            "nationality": None,
            "visa_type": None,
            "permit_type": "work permit",
            "issue_date": None,
            "expiry_date": None,
            "conditions": [None, "Authorized to work full-time"],
            "restrictions": [None],
            "reference_numbers": {"permit_number": "WP123", "bad": None},
            "deadlines": [],
            "raw_important_text": [None, "Valid work permit"],
        }
    )

    monkeypatch.setattr(document_parser, "call_gpt", lambda *args, **kwargs: fake_response)
    monkeypatch.setattr(document_parser, "extract_document_text", lambda *args, **kwargs: SimpleNamespace(text="", method="vision_ocr", confidence="medium"))
    monkeypatch.setattr(
        document_parser,
        "_pdf_to_image_messages",
        lambda _file_bytes, max_pages=3: [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
    )

    payload = document_parser.parse_document(b"%PDF-1.4 fake", "application/pdf", "Work Permit.pdf")

    assert payload["document_type"] == "work_permit"
    assert payload["issuing_authority"] == "IRCC"
    assert payload["person_name"] == ""
    assert payload["conditions"] == ["Authorized to work full-time"]
    assert payload["restrictions"] == []
    assert payload["reference_numbers"] == {"permit_number": "WP123"}
    assert payload["raw_important_text"] == ["Valid work permit"]


def test_parse_document_merges_fallback_fields_from_partial_llm_output(monkeypatch):
    import agents.document_parser as document_parser

    llm_response = json.dumps(
        {
            "document_type": "other",
            "issuing_authority": "",
            "person_name": "",
            "dob": None,
            "nationality": None,
            "visa_type": None,
            "permit_type": None,
            "issue_date": None,
            "expiry_date": None,
            "conditions": [],
            "restrictions": [],
            "reference_numbers": {},
            "deadlines": [],
            "raw_important_text": [],
        }
    )
    text = """Immigration, Refugees and Citizenship Canada
Work Permit
Name: Alex Chen
Permit Number: WP999
Expiry Date: 2026-11-01
Authorized to work full-time for any employer listed in the permit conditions."""

    monkeypatch.setattr(document_parser, "extract_document_text", lambda *args, **kwargs: SimpleNamespace(text=text, method="native_pdf_text", confidence="high"))
    monkeypatch.setattr(document_parser, "call_gpt", lambda *args, **kwargs: llm_response)

    payload = document_parser.parse_document(b"%PDF-1.4 fake", "application/pdf", "Work Permit.pdf")

    assert payload["document_type"] == "work_permit"
    assert payload["issuing_authority"] == "IRCC"
    assert payload["person_name"] == "Alex Chen"
    assert payload["expiry_date"] == "2026-11-01"
    assert payload["permit_type"] == "work permit"
    assert payload["reference_numbers"] == {"permit_number": "WP999"}
    assert payload["conditions"] == ["Authorized to work full-time for any employer listed in the permit conditions."]


def test_parse_document_renders_pdf_pages_as_images_for_low_text_pdf(monkeypatch):
    import agents.document_parser as document_parser

    monkeypatch.setattr(document_parser, "extract_document_text", lambda *args, **kwargs: SimpleNamespace(text="", method="vision_ocr", confidence="medium"))
    monkeypatch.setattr(
        document_parser,
        "_pdf_to_image_messages",
        lambda _file_bytes, max_pages=3: [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
    )

    captured_messages: list[dict] = []

    def fake_call_gpt(*, messages, **kwargs):
        captured_messages.extend(messages)
        return json.dumps(
            {
                "document_type": "passport",
                "issuing_authority": "Government of Canada",
                "person_name": "Alex Chen",
                "dob": None,
                "nationality": "India",
                "visa_type": None,
                "permit_type": None,
                "issue_date": None,
                "expiry_date": None,
                "conditions": [],
                "restrictions": [],
                "reference_numbers": {},
                "deadlines": [],
                "raw_important_text": [],
            }
        )

    monkeypatch.setattr(document_parser, "call_gpt", fake_call_gpt)

    payload = document_parser.parse_document(b"%PDF-1.4 fake", "application/pdf", "passport.pdf")

    assert payload["document_type"] == "passport"
    assert captured_messages
    content = captured_messages[0]["content"]
    assert isinstance(content, list)
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_parse_document_uses_ircc_label_parser_for_work_permit(monkeypatch):
    import agents.document_parser as document_parser

    ocr_text = """Immigration, Refugees and Citizenship Canada
WORK PERMIT/PERMIS DE TRAVAIL
Application/Demande: W307631839
UCI/UC: 1117633393
Family Name/Nom de Famille: RANJIT
Given Name(s)/Prénom(s): PRAHLAD
Date of Birth/Date de naissance: 2003/03/29
Country of Citizenship/Citoyen de: INDIA
Travel Doc No./N° du document de voyage: T8721432
Date Issued/Délivré le: 2023/03/14
Expiry Date/Date d'expiration: 2025/09/30
Employer/Employeur: UNIVERSITY OF TORONTO
Occupation/Profession: OPEN
Conditions:
1. MUST LEAVE CANADA BY 2025/09/30
Remarks/Observations:
AUTHORIZED TO UNDERTAKE EMPLOYMENT WHICH FORMS INTEGRAL PART OF STUDIES AS CERTIFIED BY THE EDUCATIONAL INSTITUTION.
"""

    monkeypatch.setattr(document_parser, "extract_document_text", lambda *args, **kwargs: SimpleNamespace(text=ocr_text, method="vision_ocr", confidence="medium"))
    monkeypatch.setattr(document_parser, "call_gpt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be used for high-confidence permit parsing")))

    payload = document_parser.parse_document(b"fake-image", "image/png", "work_permit_scan.png")

    assert payload["document_type"] == "work_permit"
    assert payload["person_name"] == "Prahlad Ranjit"
    assert payload["expiry_date"] == "2025-09-30"
    assert payload["employer"] == "UNIVERSITY OF TORONTO"
    assert payload["document_confidence"] == "high"
    assert payload["field_evidence"]["expiry_date"]["confidence"] == "high"
    assert payload["field_evidence"]["person_name"]["source"] == "label_match"
    assert any("AUTHORIZED TO UNDERTAKE EMPLOYMENT" in line for line in payload["conditions"])


def test_parse_document_recovers_expiry_from_ocr_noisy_work_permit_text(monkeypatch):
    import agents.document_parser as document_parser

    ocr_text = """IMMIGRATION, REFUGEES AND CITIZENSHIP CANADA
WORK PERMIT / PERMIS DE TRAVAIL
Family Name / Nom de Famille: RANJIT
Given Name(s) / Prenom(s): PRAHLAD
Date Issued/Delivre le: 2023/03/14
Employer/Employeur: UNIVERSITY OF TORONTO
Occupation/Profession: OPEN
Conditions:
1. MUST LEAVE CANADA BY 2025/09/30
Remarks/Observations:
AUTHORIZED TO UNDERTAKE EMPLOYMENT WHICH FORMS INTEGRAL PART OF STUDIES.
"""

    monkeypatch.setattr(document_parser, "extract_document_text", lambda *args, **kwargs: SimpleNamespace(text=ocr_text, method="vision_ocr", confidence="medium"))
    monkeypatch.setattr(document_parser, "call_gpt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be used for this OCR recovery path")))

    payload = document_parser.parse_document(b"fake-image", "image/png", "work_permit_scan.png")

    assert payload["document_type"] == "work_permit"
    assert payload["expiry_date"] == "2025-09-30"
    assert payload["field_evidence"]["expiry_date"]["source"] == "ocr_pattern_match"
    assert payload["document_confidence"] in {"medium", "high"}


def test_extract_document_text_prefers_local_macos_ocr(monkeypatch):
    import shared.ocr as ocr

    monkeypatch.setattr(ocr, "_macos_vision_ocr", lambda *args, **kwargs: ocr.OCRResult(text="WORK PERMIT\nExpiry Date: 2025/09/30", method="macos_vision_ocr", confidence="high"))
    monkeypatch.setattr(ocr, "_vision_ocr", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote vision OCR should not be used")))

    result = ocr.extract_document_text(b"fake-image", "image/png", "permit.png")

    assert result.method == "macos_vision_ocr"
    assert "2025/09/30" in result.text


def test_extract_document_text_discards_refusal_text(monkeypatch):
    import shared.ocr as ocr

    monkeypatch.setattr(ocr, "_macos_vision_ocr", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ocr,
        "_vision_ocr",
        lambda *args, **kwargs: ocr.OCRResult(
            text="I’m sorry, but I can’t view or extract text from the PDF you mentioned.",
            method="vision_ocr",
            confidence="medium",
        ),
    )

    result = ocr.extract_document_text(b"fake-pdf", "application/pdf", "permit.pdf")

    assert result.method == "vision_ocr_refused"
    assert result.text == ""


def test_synthesize_status_stays_cautious_for_expired_work_permit():
    import agents.guidance_generator as guidance_generator
    import agents.situation_reasoner as situation_reasoner

    document = {
        "document_id": "doc-1",
        "filename": "work_permit_scan.png",
        "document_type": "work_permit",
        "issuing_authority": "IRCC",
        "person_name": "Prahlad Ranjit",
        "dob": "2003-03-29",
        "nationality": "India",
        "visa_type": None,
        "permit_type": "work permit",
        "employer": "UNIVERSITY OF TORONTO",
        "occupation": "OPEN",
        "issue_date": "2023-03-14",
        "expiry_date": "2025-09-30",
        "conditions": ["AUTHORIZED TO UNDERTAKE EMPLOYMENT WHICH FORMS INTEGRAL PART OF STUDIES AS CERTIFIED BY THE EDUCATIONAL INSTITUTION."],
        "restrictions": ["MUST LEAVE CANADA BY 2025/09/30"],
        "reference_numbers": {"application_number": "W307631839", "uci": "1117633393"},
        "deadlines": [
            {
                "action": "Review work permit before expiry",
                "date": "2025-09-30",
                "urgency": "urgent",
                "days_remaining": -1,
                "source_document": "work_permit_scan.png",
            }
        ],
        "raw_important_text": ["AUTHORIZED TO UNDERTAKE EMPLOYMENT WHICH FORMS INTEGRAL PART OF STUDIES AS CERTIFIED BY THE EDUCATIONAL INSTITUTION."],
        "extraction_method": "label_parser+vision_ocr",
        "document_confidence": "high",
        "field_evidence": {
            "document_type": {"value": "work_permit", "confidence": "high", "source": "label_match", "excerpt": "WORK PERMIT/PERMIS DE TRAVAIL"},
            "person_name": {"value": "Prahlad Ranjit", "confidence": "high", "source": "label_match", "excerpt": "Given Name(s)/Prénom(s): PRAHLAD"},
            "expiry_date": {"value": "2025-09-30", "confidence": "high", "source": "label_match", "excerpt": "Expiry Date/Date d'expiration: 2025/09/30"},
        },
        "raw_text": "WORK PERMIT/PERMIS DE TRAVAIL",
    }

    profile = situation_reasoner.synthesize_status([document])
    profile = guidance_generator.generate_action_plan(profile, {"forms": {}})

    assert "cannot confirm from this upload alone" in profile["current_status"]
    assert "no valid immigration authorization" not in profile["current_status"].lower()
    assert profile["required_actions"][0]["title"] == "Verify whether a newer permit or extension filing exists"
    assert profile["required_actions"][0]["steps"]
