"use client";

import { useEffect, useMemo, useState } from "react";

import { ActionStep, RequiredAction } from "@/lib/types";

interface ActionPlanProps {
  actions: RequiredAction[];
}

function normalizeStep(step: unknown, index: number): ActionStep | null {
  if (typeof step === "string") {
    const instruction = step.trim();
    if (!instruction) {
      return null;
    }
    return {
      step_number: index + 1,
      instruction,
      form_name: null,
      form_number: null,
      official_link: null,
      fee: null,
      processing_time: null,
      tip: null,
    };
  }

  if (!step || typeof step !== "object") {
    return null;
  }

  const candidate = step as Partial<ActionStep>;
  const instruction = typeof candidate.instruction === "string" ? candidate.instruction.trim() : "";
  if (!instruction) {
    return null;
  }

  return {
    step_number: typeof candidate.step_number === "number" ? candidate.step_number : index + 1,
    instruction,
    form_name: typeof candidate.form_name === "string" ? candidate.form_name : null,
    form_number: typeof candidate.form_number === "string" ? candidate.form_number : null,
    official_link: typeof candidate.official_link === "string" ? candidate.official_link : null,
    fee: typeof candidate.fee === "string" ? candidate.fee : null,
    processing_time: typeof candidate.processing_time === "string" ? candidate.processing_time : null,
    tip: typeof candidate.tip === "string" ? candidate.tip : null,
  };
}

export default function ActionPlan({ actions }: ActionPlanProps) {
  const defaultOpen = useMemo(() => {
    const urgent = actions.find((action) => action.urgency.toLowerCase().includes("urgent"));
    return urgent?.action_id ?? actions[0]?.action_id;
  }, [actions]);

  const [openActionId, setOpenActionId] = useState<string | undefined>(defaultOpen);

  useEffect(() => {
    if (!actions.length) {
      setOpenActionId(undefined);
      return;
    }

    setOpenActionId((current) => {
      if (current && actions.some((action) => action.action_id === current)) {
        return current;
      }
      return defaultOpen;
    });
  }, [actions, defaultOpen]);

  return (
    <section className="flex h-full flex-1 flex-col overflow-hidden rounded-[20px] border border-border bg-bg-surface shadow-[0_18px_40px_rgba(60,27,5,0.06)]">
      <div className="border-b border-border px-4 py-4">
        <h3 className="font-heading text-[1.8rem] text-text-primary">Action Plan</h3>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2.5 py-2">
        <div className="space-y-2.5 pr-1">
          {actions.length === 0 && <p className="text-sm text-text-secondary">No action items detected yet from the uploaded documents.</p>}
          {actions.map((action) => {
            const isOpen = action.action_id === openActionId;
            const steps = action.steps
              .map((step, index) => normalizeStep(step as unknown, index))
              .filter((step): step is ActionStep => step !== null);
            return (
              <article key={action.action_id} className="overflow-hidden rounded-[18px] border border-border bg-bg-surface">
                <button
                  type="button"
                  onClick={() => setOpenActionId((prev) => (prev === action.action_id ? undefined : action.action_id))}
                  className="flex w-full items-center justify-between px-4 py-2.5 text-left"
                >
                  <div>
                    <p className="text-sm font-semibold text-text-primary">{action.title}</p>
                    {action.deadline && <p className="font-mono text-xs text-text-secondary">Deadline: {action.deadline}</p>}
                  </div>
                  <p className="text-xs uppercase tracking-wide text-text-secondary">{isOpen ? "Collapse" : "Expand"}</p>
                </button>

                <div
                  style={{ maxHeight: isOpen ? "440px" : "0px", transition: "max-height 250ms ease-out", overflow: "hidden" }}
                  className="border-t border-border"
                >
                  <ol className="space-y-2.5 p-3.5">
                    {steps.length === 0 && <p className="text-sm text-text-secondary">No step-by-step details are available for this action yet.</p>}
                    {steps.map((step) => (
                      <li key={`${action.action_id}-${step.step_number}`} className="rounded-lg border border-border bg-bg-raised px-3 py-2.5">
                        <p className="text-sm text-text-primary">
                          <span className="mr-2 font-mono">{step.step_number}.</span>
                          {step.instruction}
                        </p>
                        <div className="mt-1.5 flex flex-wrap gap-2 text-xs">
                          {step.form_number && (
                            <span className="rounded border border-border px-2 py-1 font-mono text-text-secondary">{step.form_number}</span>
                          )}
                          {step.fee && <span className="rounded border border-border px-2 py-1 text-text-secondary">{step.fee}</span>}
                          {step.processing_time && (
                            <span className="rounded border border-border px-2 py-1 text-text-secondary">{step.processing_time}</span>
                          )}
                          {step.official_link && (
                            <a
                              href={step.official_link}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded border border-border px-2 py-1 text-blue-700 underline-offset-2 hover:underline"
                            >
                              Official link
                            </a>
                          )}
                        </div>
                        {step.tip && <p className="mt-1.5 pl-2 text-xs italic text-text-secondary">Tip: {step.tip}</p>}
                      </li>
                    ))}
                  </ol>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
