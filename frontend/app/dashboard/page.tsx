"use client";

import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import ActionPlan from "@/components/ActionPlan";
import ChatQA from "@/components/ChatQA";
import CompletenessWarning from "@/components/CompletenessWarning";
import DeadlineTimeline from "@/components/DeadlineTimeline";
import ImpliedStatusCard from "@/components/ImpliedStatusCard";
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

    getSession(sessionId, language)
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
  }, [language, refreshKey, sessionId, setDocumentsStore, setProfileStore, setSession]);

  const profile: ImmigrationProfile | null = data?.profile ?? null;
  const documents = data?.documents ?? [];

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
      className="mx-auto flex h-screen max-h-screen w-full max-w-[1440px] flex-col px-4 py-4"
    >
      <header className="mb-3 flex items-center justify-between rounded-xl border border-border bg-bg-surface px-4 py-3">
        <div>
          <h1 className="font-heading text-3xl text-canada-red">Landed</h1>
          <p className="font-mono text-xs text-text-secondary">Session {sessionId}</p>
        </div>
        <SessionUploadPanel
          sessionId={sessionId}
          onComplete={(diff) => {
            setSessionDiff(diff);
            setRefreshKey((current) => current + 1);
          }}
        />
      </header>

      <SessionDiffBanner diff={sessionDiff} onDismiss={() => setSessionDiff(null)} />
      <CompletenessWarning completeness={data?.document_completeness} sessionId={sessionId} />

      <section className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[55fr_45fr]">
        <div className="grid min-h-0 gap-3" style={{ gridTemplateRows: "35vh 45vh" }}>
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.0 }} className="min-h-0 overflow-y-auto pr-1">
            <div className="flex min-h-full flex-col gap-3">
              <StatusDashboard
                profile={profile}
                documents={documents}
                workAuthorization={data?.work_authorization}
              />
              <ImpliedStatusCard actions={actions} />
            </div>
          </motion.div>
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="min-h-0">
            <ChatQA sessionId={sessionId} language={language} onLanguageChange={setLanguage} />
          </motion.div>
        </div>

        <div className="grid min-h-0 gap-3" style={{ gridTemplateRows: "35vh 45vh" }}>
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="min-h-0">
            <DeadlineTimeline deadlines={profile.all_deadlines} />
          </motion.div>
          <motion.div initial={false} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="min-h-0">
            <ActionPlan actions={actions} />
          </motion.div>
        </div>
      </section>
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
