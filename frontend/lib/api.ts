import {
  ChatMessage,
  ChatTranslationResponse,
  QAResponse,
  SessionResponse,
  StreamEvent,
  UploadResponse,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function parseJson<T>(response: Response): Promise<T> {
  const body = await response.text();
  let parsed: unknown = null;

  if (body) {
    try {
      parsed = JSON.parse(body);
    } catch {
      parsed = body;
    }
  }

  if (!response.ok) {
    if (parsed && typeof parsed === "object" && "detail" in parsed && typeof parsed.detail === "string") {
      throw new Error(parsed.detail);
    }
    if (parsed && typeof parsed === "object" && "error" in parsed && typeof parsed.error === "string") {
      throw new Error(parsed.error);
    }
    if (typeof parsed === "string" && parsed.trim()) {
      throw new Error(parsed);
    }
    throw new Error(`Request failed with ${response.status}`);
  }

  if (parsed && typeof parsed === "object" && "error" in parsed && typeof parsed.error === "string") {
    throw new Error(parsed.error);
  }

  return parsed as T;
}

export async function uploadDocuments(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`/api/upload`, {
    method: "POST",
    body: formData,
  });

  return parseJson<UploadResponse>(response);
}

export async function appendDocuments(sessionId: string, files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`/api/session/${sessionId}/upload`, {
    method: "POST",
    body: formData,
  });

  return parseJson<UploadResponse>(response);
}

export function streamSession(
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  onError: (message: string) => void,
): EventSource {
  const stream = new EventSource(`${API_BASE}/api/stream/${sessionId}`);
  let terminalEventSeen = false;

  const parseAndEmit = (rawData: string, fallbackType?: StreamEvent["event"]) => {
    try {
      const parsed = JSON.parse(rawData) as StreamEvent;
      if (fallbackType && !parsed.event && !parsed.type) {
        parsed.event = fallbackType;
      }
      const eventType = parsed.event ?? parsed.type;
      if (eventType === "error" || eventType === "complete") {
        terminalEventSeen = true;
      }
      onEvent(parsed);
    } catch {
      onError("Failed to parse processing update.");
    }
  };

  stream.onmessage = (message) => {
    parseAndEmit(message.data);
  };

  ["parsing", "reasoning", "planning", "error", "complete"].forEach((eventName) => {
    stream.addEventListener(eventName, (event) => {
      parseAndEmit((event as MessageEvent).data, eventName as StreamEvent["event"]);
    });
  });

  stream.onerror = () => {
    if (terminalEventSeen || stream.readyState === EventSource.CLOSED) {
      return;
    }
    onError("Unable to connect to processing stream. Please confirm the backend is running.");
    stream.close();
  };

  return stream;
}

export async function getSession(sessionId: string, language = "English"): Promise<SessionResponse> {
  const params = new URLSearchParams();
  if (language && language !== "English") {
    params.set("language", language);
  }
  const query = params.toString();

  const response = await fetch(`${API_BASE}/api/session/${sessionId}${query ? `?${query}` : ""}`, {
    cache: "no-store",
  });
  return parseJson<SessionResponse>(response);
}

export async function askQuestion(sessionId: string, question: string, language: string): Promise<QAResponse> {
  const payload = new FormData();
  payload.append("session_id", sessionId);
  payload.append("question", question);
  payload.append("language", language);

  const response = await fetch(`/api/qa`, {
    method: "POST",
    body: payload,
  });
  return parseJson<QAResponse>(response);
}

export async function translateChatHistory(messages: ChatMessage[], language: string): Promise<string[]> {
  const response = await fetch(`/api/chat/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      language,
      messages: messages.map((message) => ({
        role: message.role,
        content: message.source_content ?? message.content,
      })),
    }),
  });
  const payload = await parseJson<ChatTranslationResponse>(response);
  return payload.messages;
}
