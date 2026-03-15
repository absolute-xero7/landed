"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useState } from "react";

import ProcessingStream from "@/components/ProcessingStream";
import UploadZone from "@/components/UploadZone";
import { streamSession, uploadDocuments } from "@/lib/api";
import { StreamEvent } from "@/lib/types";
import { useSessionStore } from "@/store/useSessionStore";

type PageState = "idle" | "processing";

function timestampLine(message: string): string {
  const timestamp = new Date().toLocaleTimeString();
  return `[${timestamp}] ${message}`;
}

export default function HomePage() {
  const router = useRouter();
  const setSession = useSessionStore((state) => state.setSession);
  const setProfile = useSessionStore((state) => state.setProfile);
  const setDocuments = useSessionStore((state) => state.setDocuments);
  const resetChat = useSessionStore((state) => state.resetChat);

  const [files, setFiles] = useState<File[]>([]);
  const [state, setState] = useState<PageState>("idle");
  const [uploading, setUploading] = useState(false);
  const [streamLines, setStreamLines] = useState<string[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const onAnalyse = async () => {
    setUploading(true);
    setStreamError(null);
    setStreamLines([timestampLine("Upload started...")]);
    setProgress(5);

    try {
      const { session_id } = await uploadDocuments(files);
      setState("processing");
      setSession(session_id);
      setProfile(null);
      setDocuments([]);
      resetChat();

      const stream = streamSession(
        session_id,
        (event: StreamEvent) => {
          const eventType = event.event ?? event.type;

          if (eventType === "parsing") {
            const label = event.status === "started" ? `Parsing ${event.filename}...` : `Parsed ${event.filename}`;
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            setProgress((prev) => Math.min(prev + 12, 70));
            return;
          }

          if (eventType === "reasoning") {
            const label = event.status === "started" ? "Building immigration profile..." : "Reasoning complete.";
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            setProgress((prev) => Math.min(prev + 15, 90));
            return;
          }

          if (eventType === "planning") {
            const label = event.status === "started" ? "Generating action plans..." : "Action planning complete.";
            setStreamLines((prev) => [...prev, timestampLine(label)]);
            setProgress((prev) => Math.min(prev + 10, 95));
            return;
          }

          if (eventType === "complete") {
            setStreamLines((prev) => [...prev, timestampLine("Analysis complete.")]);
            setProgress(100);
            stream.close();
            router.push(`/dashboard?session=${session_id}`);
            return;
          }

          if (eventType === "error") {
            setStreamError(event.message ?? "Processing failed.");
            setStreamLines((prev) => [...prev, timestampLine(event.message ?? "Processing failed")]);
            stream.close();
          }
        },
        (message) => {
          setStreamError(message);
          setStreamLines((prev) => [...prev, timestampLine(message)]);
        },
      );
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col justify-center overflow-hidden px-4 py-6">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-[radial-gradient(circle_at_top,rgba(204,0,0,0.08),transparent_50%)]" />
      <div className="grid items-center gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <header className="max-w-2xl">
          <p className="inline-flex rounded-full border border-[rgba(204,0,0,0.14)] bg-white/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-canada-red shadow-[0_10px_30px_rgba(60,27,5,0.06)] backdrop-blur">
            Canadian immigration assistant
          </p>
          <h1 className="mt-4 max-w-[11ch] font-heading text-5xl leading-[0.94] text-canada-red sm:text-6xl">
            Landed
          </h1>
          <p className="mt-4 max-w-xl text-lg leading-7 text-text-primary sm:text-[1.15rem]">
            Understand your permits, visas, and deadlines in one place without reading every IRCC document line by line.
          </p>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-text-secondary">
            Upload your documents, let Landed cross-reference what is still active, and get a clear view of status, work rules, travel risk, and next steps.
          </p>

          <div className="mt-5 flex flex-wrap gap-2.5 text-sm text-text-secondary">
            {["Private", "Multilingual", "No account required", "Grounded in uploaded documents"].map((item) => (
              <span
                key={item}
                className="rounded-full border border-border bg-white/70 px-3 py-1 shadow-[0_8px_20px_rgba(60,27,5,0.04)] backdrop-blur"
              >
                {item}
              </span>
            ))}
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border bg-[rgba(255,252,248,0.8)] p-4 shadow-[0_18px_50px_rgba(60,27,5,0.06)] backdrop-blur">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-text-secondary">Reads</p>
              <p className="mt-2 text-lg text-text-primary">Permits, TRVs, passports, and IRCC letters</p>
            </div>
            <div className="rounded-2xl border border-border bg-[rgba(255,252,248,0.8)] p-4 shadow-[0_18px_50px_rgba(60,27,5,0.06)] backdrop-blur">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-text-secondary">Finds</p>
              <p className="mt-2 text-lg text-text-primary">Deadlines, travel risk, implied status, and work limits</p>
            </div>
            <div className="rounded-2xl border border-border bg-[rgba(255,252,248,0.8)] p-4 shadow-[0_18px_50px_rgba(60,27,5,0.06)] backdrop-blur">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-text-secondary">Answers</p>
              <p className="mt-2 text-lg text-text-primary">Questions in grounded plain language with sources</p>
            </div>
          </div>
        </header>

        <section className="mx-auto w-full max-w-[720px]">
        <AnimatePresence mode="wait" initial={false}>
          {state === "idle" ? (
            <motion.div key="upload" initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <UploadZone files={files} setFiles={setFiles} onSubmit={onAnalyse} submitting={uploading} error={streamError} />
            </motion.div>
          ) : (
            <motion.div
              key="processing"
              initial={false}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <ProcessingStream lines={streamLines} error={streamError} progress={progress} />
            </motion.div>
          )}
        </AnimatePresence>
        </section>
      </div>
    </main>
  );
}
