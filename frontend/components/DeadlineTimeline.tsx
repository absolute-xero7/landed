"use client";

import { useState } from "react";

import UrgencyBadge from "@/components/UrgencyBadge";
import { Deadline } from "@/lib/types";

interface DeadlineTimelineProps {
  deadlines: Deadline[];
}

const urgencyRank: Record<Deadline["urgency"], number> = {
  urgent: 0,
  upcoming: 1,
  future: 2,
};

function groupDeadlinesByDate(deadlines: Deadline[]) {
  const grouped = new Map<string, Deadline[]>();

  deadlines.forEach((deadline) => {
    const existing = grouped.get(deadline.date) ?? [];
    existing.push(deadline);
    grouped.set(deadline.date, existing);
  });

  return [...grouped.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => ({
      date,
      items,
      topUrgency: [...items].sort((a, b) => urgencyRank[a.urgency] - urgencyRank[b.urgency])[0]?.urgency ?? "future",
    }));
}

function groupBorderClass(items: Deadline[]) {
  const todayIso = new Date().toISOString().slice(0, 10);
  if (items.some((item) => item.date < todayIso)) {
    return "border-l-red-600";
  }
  if (items.some((item) => item.urgency === "urgent")) {
    return "border-l-amber-500";
  }
  return "border-l-border";
}

export default function DeadlineTimeline({ deadlines }: DeadlineTimelineProps) {
  const grouped = groupDeadlinesByDate(deadlines);
  const [openKey, setOpenKey] = useState<string | null>(null);

  return (
    <section className="flex h-full flex-1 flex-col overflow-hidden rounded-[20px] border border-border bg-bg-surface shadow-[0_18px_40px_rgba(60,27,5,0.06)]">
      <div className="border-b border-border px-4 py-4">
        <h3 className="font-heading text-[1.8rem] text-text-primary">Deadline Timeline</h3>
      </div>
      <div className="flex-1 px-2.5 py-2">
        {grouped.length === 0 && <p className="text-sm text-text-secondary">No explicit deadlines were detected in the uploaded documents.</p>}
        <ol className="space-y-2">
          {grouped.map((group) => {
            if (group.items.length === 1) {
              const deadline = group.items[0];
              const key = `${deadline.action}-${deadline.date}-${deadline.source_document}`;
              const expanded = openKey === key;
              const borderClass = groupBorderClass(group.items);

              return (
                <li
                  key={key}
                  className={`max-w-full overflow-hidden rounded-[16px] border border-border border-l-[3px] bg-bg-surface px-[14px] py-3 ${borderClass}`}
                >
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <p className="font-mono text-[13px] font-semibold tracking-[0.08em] text-text-primary">{deadline.date}</p>
                    <UrgencyBadge urgency={deadline.urgency} />
                  </div>
                  <p className="text-[13px] font-semibold leading-5 text-text-primary">{deadline.action}</p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-text-secondary">From {deadline.source_document}</p>
                  {deadline.processing_weeks_min != null && deadline.processing_weeks_max != null && deadline.recommended_apply_by && (
                    <p className="mt-1.5 text-[11px] italic leading-5 text-text-secondary">
                      {deadline.days_until_recommended != null && deadline.days_until_recommended > 0
                        ? `Processing: ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`
                        : deadline.days_remaining >= 0
                          ? "Processing: apply immediately"
                          : `Processing: ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`}
                    </p>
                  )}
                  {(deadline.consequence || deadline.consequence_action) && (
                    <>
                      <button
                        type="button"
                        onClick={() => setOpenKey((current) => (current === key ? null : key))}
                        className="mt-1 inline-flex items-center rounded-full border border-border bg-bg-surface px-3 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-raised hover:text-text-primary"
                      >
                        {expanded ? "Hide" : "What if I miss this?"}
                      </button>
                      <div
                        style={{ maxHeight: expanded ? "180px" : "0px", transition: "max-height 200ms ease-out", overflow: "hidden" }}
                        className="mt-1"
                      >
                        <div className="rounded-2xl border border-border bg-bg-raised px-3 py-2">
                          {deadline.consequence && <p className="text-sm text-text-secondary">{deadline.consequence}</p>}
                          {deadline.consequence_action && <p className="mt-2 text-sm font-semibold text-text-primary">→ {deadline.consequence_action}</p>}
                        </div>
                      </div>
                    </>
                  )}
                </li>
              );
            }

            return (
              <li
                key={group.date}
                className={`overflow-hidden rounded-[16px] border border-border border-l-[3px] bg-bg-surface ${groupBorderClass(group.items)}`}
              >
                <div className="flex items-center gap-3 px-[14px] py-3">
                  <p className="font-mono text-[13px] tracking-[0.08em] text-text-secondary">{group.date}</p>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div>
                  {group.items.map((deadline, index) => {
                    const key = `${deadline.action}-${deadline.date}-${deadline.source_document}`;
                    const expanded = openKey === key;

                    return (
                      <div key={key} className={index > 0 ? "border-t border-border" : ""}>
                        <div className="px-[14px] py-3 pl-[30px]">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-[13px] font-semibold leading-5 text-text-primary">{deadline.action}</p>
                              <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-text-secondary">From {deadline.source_document}</p>
                            </div>
                            <UrgencyBadge urgency={deadline.urgency} />
                          </div>
                          {deadline.processing_weeks_min != null && deadline.processing_weeks_max != null && deadline.recommended_apply_by && (
                            <p className="mt-1.5 text-[11px] italic leading-5 text-text-secondary">
                              {deadline.days_until_recommended != null && deadline.days_until_recommended > 0
                                ? `Processing: ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`
                                : deadline.days_remaining >= 0
                                  ? "Processing: apply immediately"
                                  : `Processing: ${deadline.processing_weeks_min}-${deadline.processing_weeks_max} weeks`}
                            </p>
                          )}
                          {(deadline.consequence || deadline.consequence_action) && (
                            <>
                              <button
                                type="button"
                                onClick={() => setOpenKey((current) => (current === key ? null : key))}
                                className="mt-1 inline-flex items-center rounded-full border border-border bg-bg-surface px-3 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-raised hover:text-text-primary"
                              >
                                {expanded ? "Hide" : "What if I miss this?"}
                              </button>
                              <div
                                style={{ maxHeight: expanded ? "180px" : "0px", transition: "max-height 200ms ease-out", overflow: "hidden" }}
                                className="mt-1"
                              >
                                <div className="rounded-2xl border border-border bg-bg-raised px-3 py-2">
                                  {deadline.consequence && <p className="text-sm text-text-secondary">{deadline.consequence}</p>}
                                  {deadline.consequence_action && <p className="mt-2 text-sm font-semibold text-text-primary">→ {deadline.consequence_action}</p>}
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
