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
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-4 py-10">
      <header className="mb-8 text-center">
        <h1 className="font-heading text-5xl text-canada-red">Landed</h1>
        <p className="mt-2 text-text-secondary">Your immigration documents, explained.</p>
        <p className="mt-2 text-sm text-text-secondary">Private · Multilingual · No account required</p>
      </header>

      <section className="mx-auto w-full max-w-[680px]">
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
    </main>
  );
}
