"use client";

import { useState } from "react";

import DocumentCard from "@/components/DocumentCard";
import UrgencyBadge from "@/components/UrgencyBadge";
import { DocumentCompleteness, ExtractedDocument, ImmigrationProfile, RequiredAction, WorkAuthorization } from "@/lib/types";

interface StatusDashboardProps {
  profile: ImmigrationProfile;
  documents: ExtractedDocument[];
  workAuthorization?: WorkAuthorization | null;
  completeness?: DocumentCompleteness | null;
  actions?: RequiredAction[];
}

function formatPermitType(value?: string | null) {
  if (!value) {
    return "Not identified";
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizePermitToken(value?: string | null) {
  if (!value) {
    return "";
  }

  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function buildStatusHeadline(profile: ImmigrationProfile) {
  const permit = profile.permit_type || "status";
  const expiry = profile.expiry_date || "unknown date";

  if (profile.days_until_expiry < 0) {
    return `${permit} expired on ${expiry}`;
  }

  return `Active ${permit} until ${expiry}`;
}

function buildStatusSupport(profile: ImmigrationProfile) {
  if (profile.current_status.includes("Temporary resident visa timing should be reviewed separately")) {
    return "Your permit appears active. Handle temporary resident visa timing separately for travel and re-entry.";
  }

  if (profile.risks.length > 0) {
    return profile.risks[0];
  }

  return "The current summary reflects the most relevant uploaded status document and key extracted dates.";
}

export default function StatusDashboard({ profile, documents, workAuthorization, completeness, actions = [] }: StatusDashboardProps) {
  const [showDocuments, setShowDocuments] = useState(false);
  const expiryNeedsVerification = documents.some(
    (document) => document.expiry_date === profile.expiry_date && document.low_confidence_fields.includes("expiry_date"),
  );
  const headline = buildStatusHeadline(profile);
  const support = buildStatusSupport(profile);
  const implied = actions.find((action) => action.implied_status?.eligible)?.implied_status;
  const workSummary = workAuthorization?.plain_english ?? null;
  const documentCount = documents.length;
  const expiryLabel = profile.days_until_expiry < 0 ? "Expired" : "Days remaining";
  const expiryDisplay = profile.days_until_expiry < 0 ? `Expired ${Math.abs(profile.days_until_expiry)} days ago` : `${profile.days_until_expiry} days remaining`;
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const fallbackPermitType = normalizePermitToken(profile.permit_type);
  const fallbackEligible = Boolean(profile.expiry_date) && !["", "trv", "passport", "eta", "eта"].includes(fallbackPermitType);
  const fallbackImplied = !implied && fallbackEligible
    ? {
        eligible: true,
        must_apply_before: profile.expiry_date,
        days_to_deadline: profile.days_until_expiry,
        explanation: "",
        warning: null,
      }
    : null;
  const impliedData = implied ?? fallbackImplied;
  const impliedDeadline = impliedData ? new Date(`${impliedData.must_apply_before}T00:00:00`) : null;
  const impliedWindowPassed = impliedDeadline ? impliedDeadline < startOfToday : false;

  return (
    <section className="rounded-[20px] border border-border bg-bg-surface p-2 shadow-[0_18px_40px_rgba(60,27,5,0.06)]">
      <div className="grid items-stretch gap-2 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col rounded-lg border border-border bg-bg-surface">
          <div className="flex items-start justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-secondary">Current status</p>
              <h2 className="mt-1 text-[1.2rem] font-semibold leading-[1.05] text-text-primary">{headline}</h2>
              <p className="mt-1 text-[13px] leading-5 text-text-secondary">{support}</p>
            </div>
            <div className="flex shrink-0 items-start gap-2">
              <UrgencyBadge urgency={profile.urgency_level} />
              <button
                type="button"
                onClick={() => setShowDocuments((prev) => !prev)}
                className="inline-flex items-center rounded-full border border-border bg-white px-3 py-1 text-xs text-text-secondary transition-colors hover:bg-bg-raised hover:text-text-primary"
              >
                {showDocuments ? "Hide documents" : "View documents"}
              </button>
            </div>
          </div>

          <div className="grid border-t border-border md:grid-cols-3">
            <div className="px-4 py-4 md:border-r md:border-border">
              <p className="text-[11px] uppercase tracking-[0.18em] text-text-secondary">{expiryLabel}</p>
              <p className="mt-1 text-[18px] font-semibold leading-6 text-text-primary">{expiryDisplay}</p>
              <p className="mt-0.5 font-mono text-[11px] text-text-secondary">{profile.expiry_date}</p>
              {expiryNeedsVerification && <p className="mt-0.5 text-[11px] text-[var(--status-warn)]">Verify expiry date</p>}
            </div>
            <div className="px-4 py-4 md:border-r md:border-border">
              <p className="text-[11px] uppercase tracking-[0.18em] text-text-secondary">Status type</p>
              <p className="mt-1 text-[18px] font-semibold leading-6 text-text-primary">{formatPermitType(profile.permit_type)}</p>
            </div>
            <div className="px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.18em] text-text-secondary">Documents</p>
              <p className="mt-1 text-[18px] font-semibold leading-6 text-text-primary">{documentCount} uploaded</p>
            </div>
          </div>
        </div>

        <div className="flex h-full self-stretch flex-col rounded-lg border border-border bg-bg-surface px-4 py-1">
          <div className="border-b border-border py-3">
            <p className="text-[10px] uppercase tracking-[0.18em] text-text-secondary">Work authorization</p>
            <p className="mt-1 text-[13px] leading-5 text-text-primary">
              {workSummary ? workSummary.split(". ")[0].replace(/\.$/, "") : "No clear work authorization summary yet."}
            </p>
          </div>
          <div className="border-b border-border py-3">
            <p className="text-[10px] uppercase tracking-[0.18em] text-text-secondary">Implied status</p>
            <p className={`mt-1 text-[13px] leading-5 ${impliedWindowPassed ? "text-[var(--status-urgent)]" : "text-text-primary"}`}>
              {impliedData
                ? impliedWindowPassed
                  ? "The implied status window for this permit has passed."
                  : `File before ${impliedData.must_apply_before} to keep implied status.`
                : "Not currently identified from the uploaded set."}
            </p>
          </div>
          <div className="py-3">
            <p className="text-[10px] uppercase tracking-[0.18em] text-text-secondary">Next focus</p>
            <p className="mt-1 text-[13px] leading-5 text-text-primary">
              {completeness?.missing.length
                ? "Add missing identity or status documents to tighten the assessment."
                : "Current uploaded set is enough for the main status summary."}
            </p>
          </div>
        </div>
      </div>

      {showDocuments && (
        <div className="mt-2 max-h-36 space-y-2 overflow-y-auto pr-1">
          {documents.map((document) => (
            <DocumentCard key={document.document_id} document={document} />
          ))}
        </div>
      )}
    </section>
  );
}
