"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import LanguageSelector from "@/components/LanguageSelector";
import { askQuestion, translateChatHistory } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import { useSessionStore } from "@/store/useSessionStore";

interface ChatQAProps {
  sessionId: string;
  language: string;
  onLanguageChange: (value: string) => void;
}

function streamWords(text: string, onUpdate: (value: string) => void, onDone: () => void) {
  const words = text.split(" ");
  let index = 0;
  const interval = setInterval(() => {
    index += 1;
    onUpdate(words.slice(0, index).join(" "));
    if (index >= words.length) {
      clearInterval(interval);
      onDone();
    }
  }, 60);
  return () => clearInterval(interval);
}

export default function ChatQA({ sessionId, language, onLanguageChange }: ChatQAProps) {
  const [question, setQuestion] = useState("");
  const messages = useSessionStore((state) => state.chatHistory);
  const addMessage = useSessionStore((state) => state.addMessage);
  const setChatHistory = useSessionStore((state) => state.setChatHistory);
  const [loading, setLoading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeStream, setActiveStream] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const streamCancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    return () => {
      if (streamCancelRef.current) {
        streamCancelRef.current();
        streamCancelRef.current = null;
      }
    };
  }, []);

  const canSend = useMemo(() => question.trim().length > 0 && !loading && !translating, [question, loading, translating]);

  const handleLanguageChange = async (nextLanguage: string) => {
    if (nextLanguage === language) {
      return;
    }

    onLanguageChange(nextLanguage);
    setError(null);

    const currentMessages = useSessionStore.getState().chatHistory;
    if (currentMessages.length === 0) {
      return;
    }

    setTranslating(true);
    try {
      const translatedMessages = await translateChatHistory(currentMessages, nextLanguage);
      const updatedMessages = currentMessages.map((message, index) => ({
        ...message,
        content: translatedMessages[index] ?? message.content,
        source_content: message.source_content ?? message.content,
      }));
      setChatHistory(updatedMessages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to translate the existing conversation.");
    } finally {
      setTranslating(false);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    setError(null);
    setLoading(true);

    const q = question.trim();
    const now = new Date().toLocaleTimeString();
    addMessage({ role: "user", content: q, source_content: q, timestamp: now });
    addMessage({ role: "assistant", content: "", source_content: "", timestamp: now });
    setQuestion("");
    const assistantIndex = useSessionStore.getState().chatHistory.length - 1;

    try {
      const response = await askQuestion(sessionId, q, language);
      const answer = response.answer;

      setActiveStream(true);
      if (streamCancelRef.current) {
        streamCancelRef.current();
        streamCancelRef.current = null;
      }

      const stop = streamWords(
        answer,
        (partial) => {
          useSessionStore.setState((state) => {
            const prev = state.chatHistory;
            const copy = [...prev];
            copy[assistantIndex] = {
              ...copy[assistantIndex],
              content: partial,
              source_content: answer,
              timestamp: new Date().toLocaleTimeString(),
            };
            return { chatHistory: copy };
          });
        },
        () => {
          setActiveStream(false);
          setLoading(false);
        },
      );
      streamCancelRef.current = stop;
    } catch (err) {
      useSessionStore.setState((state) => ({
        chatHistory: state.chatHistory.filter((_, index) => index !== assistantIndex),
      }));
      setError(err instanceof Error ? err.message : "Unable to fetch answer. Please try again.");
      setLoading(false);
    }
  };

  return (
    <section className="flex h-full flex-col rounded-2xl border border-border bg-bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-heading text-xl text-text-primary">Question & Answer</h3>
        <LanguageSelector value={language} onChange={handleLanguageChange} disabled={loading || activeStream || translating} />
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-lg border border-border bg-white p-3">
        {messages.length === 0 && (
          <p className="text-sm text-text-secondary">Ask a question about this person's current immigration situation. Changing the selector retranslates the full conversation.</p>
        )}

        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={message.role === "user" ? "text-right" : "text-left"}>
            <p className="text-xs uppercase tracking-wide text-text-secondary">{message.role}</p>
            <p className="text-sm text-text-primary">{message.content || (activeStream && message.role === "assistant" ? "|" : "")}</p>
            <p className="font-mono text-xs text-text-secondary">{message.timestamp}</p>
          </div>
        ))}
      </div>

      {translating && <p className="mt-2 text-sm text-text-secondary">Translating conversation...</p>}
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}

      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Can this person work part-time while studying?"
          className="flex-1 rounded-lg border border-border bg-white px-3 py-2 text-sm text-text-primary focus:border-border-strong focus:outline-none"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="rounded-lg bg-text-primary px-4 py-2 text-sm text-bg-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </section>
  );
}
