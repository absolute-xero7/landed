"use client";

import { useState } from "react";
import { Paperclip, Upload, X } from "lucide-react";
import { useDropzone } from "react-dropzone";

import { appendDocuments, streamSession } from "@/lib/api";
import { SessionDiff, StreamEvent } from "@/lib/types";

interface SessionUploadPanelProps {
  sessionId: string;
  onComplete: (diff: SessionDiff | null) => void;
}

const MAX_FILES = 10;
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

function timestampLine(message: string): string {
  const timestamp = new Date().toLocaleTimeString();
  return `[${timestamp}] ${message}`;
}

export default function SessionUploadPanel({ sessionId, onComplete }: SessionUploadPanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [streamLines, setStreamLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const dropzone = useDropzone({
    onDrop: (acceptedFiles) => {
      setFiles((current) => [...current, ...acceptedFiles].slice(0, MAX_FILES));
    },
    maxFiles: MAX_FILES,
    maxSize: MAX_SIZE_BYTES,
    multiple: true,
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
  });

  const onSubmit = async () => {
    if (!files.length) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setStreamLines([timestampLine("Uploading additional documents...")]);

    try {
      await appendDocuments(sessionId, files);
      const stream = streamSession(
        sessionId,
        (event: StreamEvent) => {
          const eventType = event.event ?? event.type;

          if (eventType === "parsing") {
            const label = event.status === "started" ? `Parsing ${event.filename}...` : `Parsed ${event.filename}`;
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            return;
          }

          if (eventType === "reasoning") {
            const label = event.status === "started" ? "Refreshing immigration profile..." : "Reasoning complete.";
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            return;
          }

          if (eventType === "planning") {
            const label = event.status === "started" ? "Updating action plan..." : "Action plan updated.";
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            return;
          }

          if (eventType === "complete") {
            setStreamLines((prev) => [...prev, timestampLine("Session updated.")]);
            stream.close();
            setFiles([]);
            setExpanded(false);
            setSubmitting(false);
            onComplete(event.session_diff ?? null);
            return;
          }

          if (eventType === "error") {
            const message = event.message ?? "Processing failed.";
            setError(message);
            setStreamLines((prev) => [...prev, timestampLine(message)]);
            setSubmitting(false);
            stream.close();
          }
        },
        (message) => {
          setError(message);
          setStreamLines((prev) => [...prev, timestampLine(message)]);
          setSubmitting(false);
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex justify-end">
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors ${
            expanded ? "border-border-strong bg-bg-raised text-text-primary" : "border-border bg-white text-text-primary hover:bg-bg-raised"
          }`}
        >
          <Paperclip className="h-4 w-4" />
          <span>{expanded ? "Close uploader" : "Add documents"}</span>
          {!!files.length && (
            <span className="rounded-full bg-text-primary px-2 py-0.5 font-mono text-[11px] text-bg-surface">
              {files.length}
            </span>
          )}
        </button>

      {expanded && (
        <div className="absolute right-0 top-[calc(100%+0.75rem)] z-20 w-[380px] max-w-[min(380px,calc(100vw-2rem))] rounded-2xl border border-border bg-bg-surface p-4 shadow-[0_20px_50px_rgba(0,0,0,0.08)]">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="font-medium text-text-primary">Add documents to this session</p>
              <p className="mt-1 text-xs text-text-secondary">Upload more files and rerun the analysis without leaving the dashboard.</p>
            </div>
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="rounded-full p-1 text-text-secondary hover:bg-bg-raised hover:text-text-primary"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div
            {...dropzone.getRootProps()}
            className={`cursor-pointer rounded-2xl border border-dashed p-5 text-center transition-colors ${
              dropzone.isDragActive ? "border-canada-red bg-red-50/40" : "border-border bg-white hover:bg-bg-raised"
            }`}
          >
            <input {...dropzone.getInputProps()} />
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-bg-raised">
              <Upload className="h-4 w-4 text-text-secondary" />
            </div>
            <p className="mt-3 text-sm text-text-primary">Drop more files here, or click to browse</p>
            <p className="mt-1 text-xs text-text-secondary">PDF, PNG, JPG, JPEG. Max 10 files total per session.</p>
          </div>

          {!!files.length && (
            <div className="mt-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs uppercase tracking-wide text-text-secondary">Queued files</p>
                <p className="font-mono text-xs text-text-secondary">{files.length} selected</p>
              </div>
              <div className="max-h-32 space-y-2 overflow-y-auto pr-1">
              {files.map((file, index) => (
                <div key={`${file.name}-${index}`} className="flex items-center justify-between rounded-xl border border-border bg-white px-3 py-2">
                  <span className="truncate pr-3 text-sm text-text-primary">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
                    className="text-xs text-text-secondary hover:text-text-primary"
                  >
                    Remove
                  </button>
                </div>
              ))}
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="rounded-xl border border-border px-3 py-2 text-sm text-text-secondary hover:bg-bg-raised hover:text-text-primary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={!files.length || submitting}
              className="flex-1 rounded-xl bg-text-primary px-4 py-2 text-sm text-bg-surface transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? "Processing..." : "Add to session"}
            </button>
          </div>

          {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

          {!!streamLines.length && (
            <div className="mt-3 rounded-xl border border-border bg-white p-3">
              <p className="mb-2 text-xs uppercase tracking-wide text-text-secondary">Processing</p>
              <div className="max-h-28 overflow-y-auto space-y-1">
              {streamLines.map((line, index) => (
                <p key={`${line}-${index}`} className="font-mono text-xs text-text-secondary">
                  {line}
                </p>
              ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
