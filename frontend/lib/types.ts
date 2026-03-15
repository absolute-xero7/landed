export type Urgency = "urgent" | "upcoming" | "future";
export type ProfileUrgency = "critical" | "urgent" | "normal";

export interface Deadline {
  action: string;
  date: string;
  urgency: Urgency;
  days_remaining: number;
  source_document: string;
  recommended_apply_by?: string | null;
  latest_apply_by?: string | null;
  estimated_completion?: string | null;
  days_until_recommended?: number | null;
  is_overdue?: boolean | null;
  processing_note?: string | null;
  processing_weeks_min?: number | null;
  processing_weeks_max?: number | null;
  consequence?: string | null;
  consequence_action?: string | null;
}

export interface ActionStep {
  step_number: number;
  instruction: string;
  form_name: string | null;
  form_number: string | null;
  official_link: string | null;
  fee: string | null;
  processing_time: string | null;
  tip: string | null;
}

export interface FieldEvidence {
  value: string | null;
  confidence: "low" | "medium" | "high" | string;
  source: string;
  excerpt: string | null;
}

export interface RequiredAction {
  action_id: string;
  title: string;
  urgency: Urgency | string;
  deadline: string | null;
  steps: ActionStep[];
  implied_status?: ImpliedStatus | null;
}

export interface ExtractedDocument {
  document_id: string;
  filename: string;
  document_type: "study_permit" | "trv" | "work_permit" | "ircc_letter" | "passport" | "other";
  issuing_authority: string;
  person_name: string;
  dob: string | null;
  nationality: string | null;
  visa_type: string | null;
  permit_type: string | null;
  employer: string | null;
  occupation: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  conditions: string[];
  restrictions: string[];
  reference_numbers: Record<string, string>;
  deadlines: Deadline[];
  raw_important_text: string[];
  extraction_method: string;
  document_confidence: "low" | "medium" | "high" | string;
  field_evidence: Record<string, FieldEvidence>;
  raw_text: string | null;
  low_confidence_fields: string[];
}

export interface ImpliedStatus {
  eligible: boolean;
  must_apply_before: string;
  days_to_deadline: number;
  explanation: string;
  warning: string | null;
}

export interface DocumentCompletenessItem {
  type: string;
  reason: string;
}

export interface DocumentCompleteness {
  complete: boolean;
  missing: DocumentCompletenessItem[];
  uploaded_count: number;
  uploaded_types: string[];
}

export interface WorkAuthorization {
  authorized: boolean;
  on_campus: boolean;
  off_campus_hours_per_week: number | null;
  off_campus_hours_per_month: number | null;
  full_time_during_breaks: boolean;
  coop_authorized: boolean;
  source_document: string | null;
  plain_english: string;
  conditions_raw: string[];
  key_points?: string[];
  policy_note?: string | null;
  policy_effective_date?: string | null;
  policy_source_url?: string | null;
}

export interface SessionDiff {
  previous_document_count: number;
  previous_document_types: string[];
  previous_deadlines: Deadline[];
  added_documents: string[];
  removed_documents: string[];
  new_deadlines_found: Deadline[];
  status_changed: boolean;
  summary: string;
}

export interface ImmigrationProfile {
  current_status: string;
  permit_type: string;
  authorized_activities: string[];
  expiry_date: string;
  days_until_expiry: number;
  urgency_level: ProfileUrgency;
  all_deadlines: Deadline[];
  required_actions: RequiredAction[];
  risks: string[];
}

export interface UploadResponse {
  session_id: string;
}

export interface SessionResponse {
  profile: ImmigrationProfile | null;
  documents: ExtractedDocument[];
  document_completeness?: DocumentCompleteness | null;
  work_authorization?: WorkAuthorization | null;
}

export interface QAResponse {
  answer: string;
}

export interface ChatTranslationResponse {
  messages: string[];
}

export interface TranslateResponse {
  translated_status: string | null;
  translated_actions: RequiredAction[] | null;
  translated_profile_text: string | null;
}

export interface StreamEvent {
  type?: "connected" | "parsing" | "reasoning" | "planning" | "profile" | "error" | "complete";
  event?: "parsing" | "reasoning" | "planning" | "error" | "complete";
  filename?: string;
  status?: "started" | "complete";
  document_type?: string;
  session_id?: string;
  message?: string;
  profile?: ImmigrationProfile;
  session_diff?: SessionDiff | null;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  source_content?: string;
}
