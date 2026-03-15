"use client";

import { useEffect } from "react";

import UrgencyBadge from "@/components/UrgencyBadge";
import { SessionDiff } from "@/lib/types";

interface SessionDiffBannerProps {
  diff: SessionDiff | null;
  onDismiss: () => void;
}

export default function SessionDiffBanner({ diff, onDismiss }: SessionDiffBannerProps) {
  useEffect(() => {
    if (!diff) {
      return;
    }
    const timeout = window.setTimeout(onDismiss, 8000);
    return () => window.clearTimeout(timeout);
  }, [diff, onDismiss]);

  if (!diff) {
    return null;
  }

  return (
    <section className="mb-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-950">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{diff.summary}</p>
          {diff.status_changed && <p className="mt-1">Your status summary has been updated.</p>}
          {diff.new_deadlines_found.length > 0 && (
            <div className="mt-2 space-y-2">
              {diff.new_deadlines_found.map((deadline) => (
                <div key={`${deadline.action}-${deadline.date}`} className="flex items-center gap-2">
                  <UrgencyBadge urgency={deadline.urgency} />
                  <span>{deadline.action} by {deadline.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <button type="button" onClick={onDismiss} className="text-sm text-blue-950">
          ×
        </button>
      </div>
    </section>
  );
}
