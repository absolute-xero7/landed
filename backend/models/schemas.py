from __future__ import annotations

from pydantic import BaseModel, Field


class Deadline(BaseModel):
    action: str
    date: str
    urgency: str
    days_remaining: int
    source_document: str
    recommended_apply_by: str | None = None
    latest_apply_by: str | None = None
    estimated_completion: str | None = None
    days_until_recommended: int | None = None
    is_overdue: bool | None = None
    processing_note: str | None = None
    processing_weeks_min: int | None = None
    processing_weeks_max: int | None = None
    consequence: str | None = None
    consequence_action: str | None = None


class ActionStep(BaseModel):
    step_number: int
    instruction: str
    form_name: str | None = None
    form_number: str | None = None
    official_link: str | None = None
    fee: str | None = None
    processing_time: str | None = None
    tip: str | None = None


class FieldEvidence(BaseModel):
    value: str | None = None
    confidence: str
    source: str
    excerpt: str | None = None


class UploadArtifact(BaseModel):
    filename: str
    mime_type: str
    data_base64: str


class RequiredAction(BaseModel):
    action_id: str
    title: str
    urgency: str
    deadline: str | None = None
    steps: list[ActionStep]
    implied_status: dict | None = None


class ExtractedDocument(BaseModel):
    document_id: str
    filename: str
    document_type: str
    issuing_authority: str
    person_name: str
    dob: str | None = None
    nationality: str | None = None
    visa_type: str | None = None
    permit_type: str | None = None
    employer: str | None = None
    occupation: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    conditions: list[str]
    restrictions: list[str]
    reference_numbers: dict[str, str]
    deadlines: list[Deadline]
    raw_important_text: list[str]
    extraction_method: str = "unknown"
    document_confidence: str = "low"
    field_evidence: dict[str, FieldEvidence] = Field(default_factory=dict)
    raw_text: str | None = None
    low_confidence_fields: list[str] = Field(default_factory=list)


class ImmigrationProfile(BaseModel):
    current_status: str
    permit_type: str
    authorized_activities: list[str]
    expiry_date: str
    days_until_expiry: int
    urgency_level: str
    all_deadlines: list[Deadline]
    required_actions: list[RequiredAction]
    risks: list[str]


class ChatTranslationMessage(BaseModel):
    role: str
    content: str


class ChatTranslationRequest(BaseModel):
    messages: list[ChatTranslationMessage]
    language: str = "English"


class ChatTranslationResponse(BaseModel):
    messages: list[str]
