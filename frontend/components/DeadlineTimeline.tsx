"use client";

import { useState } from "react";

import UrgencyBadge from "@/components/UrgencyBadge";
import { Deadline } from "@/lib/types";

interface DeadlineTimelineProps {
  deadlines: Deadline[];
}

const borderClasses: Record<Deadline["urgency"], string> = {
  urgent: "border-l-red-600",
  upcoming: "border-l-amber-500",
  future: "border-l-blue-500",
};

export default function DeadlineTimeline({ deadlines }: DeadlineTimelineProps) {
  const sorted = [...deadlines].sort((a, b) => a.date.localeCompare(b.date));
  const [openKey, setOpenKey] = useState<string | null>(null);

  return (
    <section className="h-full rounded-2xl border border-border bg-bg-surface p-5">
      <h3 className="font-heading text-xl text-text-primary">Deadline Timeline</h3>
      <div className="mt-4 h-[calc(100%-2rem)] overflow-y-auto pr-1">
        {sorted.length === 0 && <p className="text-sm text-text-secondary">No explicit deadlines were detected in the uploaded documents.</p>}
        <ol className="space-y-3">
          {sorted.map((deadline) => {
            const key = `${deadline.action}-${deadline.date}`;
            const expanded = openKey === key;
            return (
              <li
                key={key}
                className={`rounded-lg border border-border border-l-4 bg-white p-3 ${borderClasses[deadline.urgency]} ${
                  deadline.urgency === "urgent" ? "animate-subtlePulse" : ""
                }`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <p className="font-mono text-sm font-semibold text-text-primary">{deadline.date}</p>
                  <UrgencyBadge urgency={deadline.urgency} />
                </div>
                <p className="text-sm text-text-primary">{deadline.action}</p>
                <p className="mt-1 text-xs text-text-secondary">From: {deadline.source_document}</p>
                {deadline.processing_weeks_min != null && deadline.processing_weeks_max != null && deadline.recommended_apply_by && (
                  <p className="mt-2 font-mono text-xs text-[var(--status-warn)]">
                    {deadline.days_until_recommended != null && deadline.days_until_recommended > 0
                      ? `Apply by ${deadline.recommended_apply_by} to be safe — processing takes ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`
                      : deadline.days_remaining >= 0
                        ? "⚠ Recommended application window has passed — apply immediately"
                        : `Processing takes ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`}
                  </p>
                )}
                {(deadline.consequence || deadline.consequence_action) && (
                  <>
                    <button
                      type="button"
                      onClick={() => setOpenKey((current) => (current === key ? null : key))}
                      className="mt-3 text-xs text-text-secondary underline-offset-2 hover:underline"
                    >
                      {expanded ? "Hide" : "What if I miss this?"}
                    </button>
                    <div
                      style={{ maxHeight: expanded ? "180px" : "0px", transition: "max-height 200ms ease-out", overflow: "hidden" }}
                      className="mt-2"
                    >
                      <div className="rounded-lg border border-border bg-bg-raised px-3 py-2">
                        {deadline.consequence && <p className="text-sm text-text-secondary">{deadline.consequence}</p>}
                        {deadline.consequence_action && <p className="mt-2 text-sm font-semibold text-text-primary">→ {deadline.consequence_action}</p>}
                      </div>
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
