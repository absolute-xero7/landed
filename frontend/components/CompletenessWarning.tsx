"use client";

import { useEffect, useState } from "react";

import { DocumentCompleteness } from "@/lib/types";

interface CompletenessWarningProps {
  completeness: DocumentCompleteness | null | undefined;
  sessionId: string;
}

export default function CompletenessWarning({ completeness, sessionId }: CompletenessWarningProps) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    setDismissed(window.sessionStorage.getItem(`landed-completeness-dismissed:${sessionId}`) === "true");
  }, [sessionId]);

  if (!completeness || dismissed || completeness.missing.length === 0) {
    return null;
  }

  return (
    <section className="rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-[0_14px_30px_rgba(60,27,5,0.04)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">For a complete analysis, consider uploading:</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {completeness.missing.map((item) => (
              <span
                key={item.type}
                title={item.reason}
                className="rounded-full border border-amber-200 bg-white px-2 py-1 font-mono text-xs uppercase tracking-wide text-[var(--status-warn)]"
              >
                {item.type}
              </span>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            window.sessionStorage.setItem(`landed-completeness-dismissed:${sessionId}`, "true");
            setDismissed(true);
          }}
          className="text-sm text-amber-900"
        >
          ×
        </button>
      </div>
    </section>
  );
}
