"use client";

import { useState } from "react";

import DocumentCard from "@/components/DocumentCard";
import UrgencyBadge from "@/components/UrgencyBadge";
import WorkAuthCard from "@/components/WorkAuthCard";
import { ExtractedDocument, ImmigrationProfile, WorkAuthorization } from "@/lib/types";

interface StatusDashboardProps {
  profile: ImmigrationProfile;
  documents: ExtractedDocument[];
  workAuthorization?: WorkAuthorization | null;
}

export default function StatusDashboard({ profile, documents, workAuthorization }: StatusDashboardProps) {
  const [showDocuments, setShowDocuments] = useState(false);
  const expiryNeedsVerification = documents.some(
    (document) => document.expiry_date === profile.expiry_date && document.low_confidence_fields.includes("expiry_date"),
  );

  return (
    <section className="flex min-h-0 flex-col rounded-2xl border border-border bg-bg-surface p-5">
      {profile.urgency_level !== "normal" && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Action recommended soon. One or more statuses are approaching expiry.
        </div>
      )}

      <div className="mb-4 flex flex-col gap-3">
        <h2 className="font-heading text-2xl leading-tight text-text-primary">
          {profile.current_status}
        </h2>
        <div className="self-start">
          <UrgencyBadge urgency={profile.urgency_level} />
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-border bg-bg-raised p-3">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Days until nearest expiry</p>
        <p className="font-mono text-4xl text-text-primary">{profile.days_until_expiry}</p>
        <p className="font-mono text-sm text-text-secondary">{profile.expiry_date}</p>
        {expiryNeedsVerification && <p className="mt-1 text-xs text-[var(--status-warn)]">⚠ Expiry date may need verification</p>}
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <p className="text-sm font-medium text-text-primary">Authorized to</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-secondary">
          {profile.authorized_activities.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>

        <WorkAuthCard workAuthorization={workAuthorization} />

        {profile.risks.length > 0 && (
          <>
            <p className="mt-4 text-sm font-medium text-text-primary">Risks</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-red-700">
              {profile.risks.map((risk, index) => (
                <li key={`${risk}-${index}`}>{risk}</li>
              ))}
            </ul>
          </>
        )}

        <button
          type="button"
          onClick={() => setShowDocuments((prev) => !prev)}
          className="mt-4 text-sm text-text-secondary underline-offset-2 hover:underline"
        >
          {showDocuments ? "Hide documents" : `View documents (${documents.length})`}
        </button>

        {showDocuments && (
          <div className="mt-3 space-y-2">
            {documents.map((document) => (
              <DocumentCard key={document.document_id} document={document} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
