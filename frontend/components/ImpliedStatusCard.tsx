"use client";

import { RequiredAction } from "@/lib/types";

interface ImpliedStatusCardProps {
  actions: RequiredAction[];
}

export default function ImpliedStatusCard({ actions }: ImpliedStatusCardProps) {
  const implied = actions.find((action) => action.implied_status?.eligible)?.implied_status;

  if (!implied) {
    return null;
  }

  return (
    <section className="rounded-[28px] border border-border bg-bg-surface p-5 shadow-[0_18px_36px_rgba(60,27,5,0.06)]">
      <h3 className="font-heading text-xl text-text-primary">Implied Status</h3>
      <p className="mt-2 text-sm text-text-secondary">{implied.explanation}</p>
      {implied.warning && (
        <div className="mt-3 border-l-4 border-amber-400 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {implied.warning}
        </div>
      )}
    </section>
  );
}
