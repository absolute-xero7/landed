"use client";

import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import ActionPlan from "@/components/ActionPlan";
import ChatLauncher from "@/components/ChatLauncher";
import DeadlineTimeline from "@/components/DeadlineTimeline";
import SessionUploadPanel from "@/components/SessionUploadPanel";
import SessionDiffBanner from "@/components/SessionDiffBanner";
import StatusDashboard from "@/components/StatusDashboard";
import { getSession } from "@/lib/api";
import { ImmigrationProfile, RequiredAction, SessionDiff, SessionResponse } from "@/lib/types";
import { useSessionStore } from "@/store/useSessionStore";

function DashboardContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");

  const language = useSessionStore((state) => state.language);
  const setLanguage = useSessionStore((state) => state.setLanguage);
  const setSession = useSessionStore((state) => state.setSession);
  const setProfileStore = useSessionStore((state) => state.setProfile);
  const setDocumentsStore = useSessionStore((state) => state.setDocuments);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SessionResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sessionDiff, setSessionDiff] = useState<SessionDiff | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session id.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    getSession(sessionId)
      .then((response) => {
        setData(response);
        setSession(sessionId);
        setProfileStore(response.profile);
        setDocumentsStore(response.documents);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load session.");
      })
      .finally(() => setLoading(false));
  }, [refreshKey, sessionId, setDocumentsStore, setProfileStore, setSession]);

  const profile: ImmigrationProfile | null = data?.profile ?? null;
  const documents = data?.documents ?? [];
  const missingHeaderDocs = data?.document_completeness?.missing ?? [];

  const actions = useMemo(() => {
    if (!profile) {
      return [];
    }
    return profile.required_actions;
  }, [profile]);

  if (loading) {
    return <main className="p-6 text-text-secondary">Loading dashboard...</main>;
  }

  if (error || !profile || !sessionId) {
    return (
      <main className="p-6 text-red-700">
        {error || "Session profile unavailable. Please return to upload and try again."}
      </main>
    );
  }

  return (
    <motion.main
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="mx-auto flex h-screen max-h-screen w-full max-w-[1480px] flex-col overflow-hidden px-4 py-3"
    >
      <header className="mb-2.5 shrink-0 rounded-[24px] border border-border bg-bg-surface px-4 py-3 shadow-[0_16px_36px_rgba(60,27,5,0.06)]">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-secondary">Canadian immigration assistant</p>
            <h1 className="mt-1 font-heading text-[2.2rem] leading-none text-canada-red">Landed</h1>
            <p className="mt-1 text-sm text-text-secondary">Status, deadlines, and next steps in one place.</p>
            <p className="mt-1.5 font-mono text-xs text-text-secondary">Session {sessionId}</p>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-2">
            <SessionUploadPanel
              sessionId={sessionId}
              onComplete={(diff) => {
                setSessionDiff(diff);
                setRefreshKey((current) => current + 1);
              }}
            />
            {missingHeaderDocs.length > 0 && (
              <div className="flex flex-wrap items-center justify-end gap-1.5 pr-6 text-right">
                <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--status-warn)]" />
                <span className="text-[11px] text-text-secondary">Upload:</span>
                {missingHeaderDocs.map((item) => (
                  <span
                    key={item.type}
                    title={item.reason}
                    className="rounded-full border border-amber-200 bg-amber-50/85 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide text-[var(--status-warn)]"
                  >
                    {item.type}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </header>

      <SessionDiffBanner diff={sessionDiff} onDismiss={() => setSessionDiff(null)} />
      <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.0 }} className="shrink-0">
        <StatusDashboard
          profile={profile}
          documents={documents}
          workAuthorization={data?.work_authorization}
          completeness={data?.document_completeness}
          actions={actions}
        />
      </motion.div>

      <section className="mt-2.5 grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="min-h-0">
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.05 }} className="h-full min-h-0">
            <DeadlineTimeline deadlines={profile.all_deadlines} />
          </motion.div>
        </div>
        <div className="min-h-0">
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="h-full min-h-0">
            <ActionPlan actions={actions} />
          </motion.div>
        </div>
      </section>

      <ChatLauncher sessionId={sessionId} language={language} onLanguageChange={setLanguage} />
    </motion.main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<main className="p-6 text-text-secondary">Loading dashboard...</main>}>
      <DashboardContent />
    </Suspense>
  );
}
