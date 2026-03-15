"use client";

import { useState } from "react";

import { ExtractedDocument } from "@/lib/types";

interface DocumentCardProps {
  document: ExtractedDocument;
}

export default function DocumentCard({ document }: DocumentCardProps) {
  const [open, setOpen] = useState(false);
  const importantEvidence = [
    ["person_name", "Name"],
    ["expiry_date", "Expiry"],
    ["issue_date", "Issued"],
    ["employer", "Employer"],
    ["occupation", "Occupation"],
  ].filter(([key]) => document.field_evidence[key]);
  const isLowConfidence = (field: string) => document.low_confidence_fields.includes(field);
  const warning = (field: string) =>
    isLowConfidence(field) ? (
      <span
        title="This field was extracted with low confidence — verify against your original document"
        className="ml-1 text-[10px] text-[var(--status-warn)]"
      >
        ⚠
      </span>
    ) : null;

  return (
    <article className="rounded-[24px] border border-border bg-bg-surface p-3 shadow-[0_12px_30px_rgba(60,27,5,0.04)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-text-primary">{document.filename}</p>
          <div className="mt-1 flex flex-wrap gap-2">
            <p className="inline-flex rounded-md border border-border px-2 py-0.5 font-mono text-xs uppercase text-text-mono">
              {document.document_type}
            </p>
            <p className="inline-flex rounded-md border border-border px-2 py-0.5 font-mono text-xs uppercase text-text-mono">
              confidence: {document.document_confidence}
            </p>
          </div>
          {document.expiry_date && <p className="mt-1 font-mono text-xs text-text-secondary">Expiry: {document.expiry_date}{warning("expiry_date")}</p>}
        </div>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="text-sm text-text-secondary underline-offset-2 hover:underline"
        >
          {open ? "Hide" : "View extracted data"}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-2 border-t border-border pt-2 text-sm text-text-secondary">
          <p>Authority: {document.issuing_authority || "Unknown"}{warning("issuing_authority")}</p>
          <p>Person: {document.person_name || "Unknown"}{warning("person_name")}</p>
          <p>Permit: {document.permit_type || "N/A"}{warning("permit_type")}</p>
          <p>Visa: {document.visa_type || "N/A"}</p>
          <p>Employer: {document.employer || "N/A"}{warning("employer")}</p>
          <p>Occupation: {document.occupation || "N/A"}{warning("occupation")}</p>
          <p>Extraction method: {document.extraction_method}</p>
          {importantEvidence.length > 0 && (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <p className="font-medium text-text-primary">Field evidence</p>
              {importantEvidence.map(([key, label]) => {
                const evidence = document.field_evidence[key];
                return (
                  <div key={key} className="rounded-md bg-bg px-3 py-2">
                    <p className="text-text-primary">
                      {label}: {evidence.value || "Unavailable"}{warning(key)}
                    </p>
                    <p className="font-mono text-xs uppercase">
                      {evidence.confidence} via {evidence.source}
                    </p>
                    {evidence.excerpt && <p className="mt-1 text-xs">{evidence.excerpt}</p>}
                  </div>
                );
              })}
            </div>
          )}
          {document.deadlines.length > 0 && (
            <ul className="list-disc space-y-1 pl-5">
              {document.deadlines.map((deadline) => (
                <li key={`${deadline.action}-${deadline.date}`}>
                  <span className="font-medium text-text-primary">{deadline.action}</span> by {deadline.date}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}
