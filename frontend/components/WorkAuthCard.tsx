"use client";

import { WorkAuthorization } from "@/lib/types";

interface WorkAuthCardProps {
  workAuthorization: WorkAuthorization | null | undefined;
}

export default function WorkAuthCard({ workAuthorization }: WorkAuthCardProps) {
  if (!workAuthorization || typeof workAuthorization.authorized !== "boolean") {
    return null;
  }

  return (
    <section className="mt-4 rounded-xl border border-border bg-bg-raised p-3">
      <h3 className="font-heading text-lg text-text-primary">Work Authorization</h3>
      <p className="mt-2 text-sm text-text-secondary">{workAuthorization.plain_english}</p>
      {workAuthorization.policy_note && (
        <p className="mt-2 text-xs text-text-secondary">
          Cross-checked with IRCC guidance{workAuthorization.policy_effective_date ? ` effective ${workAuthorization.policy_effective_date}` : ""}.
        </p>
      )}
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-text-secondary sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-white px-3 py-2">
          <p className="font-medium text-text-primary">On-campus</p>
          <p>{workAuthorization.on_campus ? "Yes" : "No clear authorization"}</p>
        </div>
        <div className="rounded-lg border border-border bg-white px-3 py-2">
          <p className="font-medium text-text-primary">Off-campus</p>
          <p>{workAuthorization.off_campus_hours_per_week ? `${workAuthorization.off_campus_hours_per_week} hrs/week` : "No clear limit found"}</p>
        </div>
        <div className="rounded-lg border border-border bg-white px-3 py-2">
          <p className="font-medium text-text-primary">Breaks / Co-op</p>
          <p>
            {workAuthorization.full_time_during_breaks ? "Full-time breaks" : "No break rule found"}
            {workAuthorization.coop_authorized ? " · Co-op yes" : ""}
          </p>
        </div>
      </div>
      {workAuthorization.source_document && (
        <p className="mt-2 text-xs text-text-secondary">Extracted from: {workAuthorization.source_document}</p>
      )}
      {workAuthorization.policy_source_url && (
        <p className="mt-1 text-xs text-text-secondary">
          Policy source:{" "}
          <a className="underline underline-offset-2" href={workAuthorization.policy_source_url} target="_blank" rel="noreferrer">
            IRCC study permit work rules
          </a>
        </p>
      )}
    </section>
  );
}
