"use client";

import { motion } from "framer-motion";
import { useEffect, useRef } from "react";

interface ProcessingStreamProps {
  lines: string[];
  error: string | null;
  progress: number;
}

export default function ProcessingStream({ lines, error, progress }: ProcessingStreamProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines]);

  return (
    <section className="w-full rounded-[28px] border border-border bg-[rgba(255,252,248,0.95)] p-6 shadow-[0_24px_80px_rgba(60,27,5,0.1)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-text-secondary">Processing session</p>
          <h2 className="mt-2 font-heading text-3xl text-text-primary">Reading your documents</h2>
        </div>
        <div className="rounded-full border border-border bg-white/80 px-3 py-1.5 font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
          {Math.max(progress, 5)}%
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-full bg-bg-raised">
        <div
          className="h-[6px] rounded-full bg-[linear-gradient(90deg,rgba(204,0,0,0.55),rgba(197,106,19,0.85))]"
          style={{ width: `${Math.max(progress, 5)}%`, transition: "width 350ms ease" }}
        />
      </div>
      <div className="mt-5 rounded-[24px] border border-border bg-[linear-gradient(135deg,rgba(255,255,255,0.88),rgba(241,233,220,0.72))] p-4">
        <p className="text-sm leading-6 text-text-secondary">
          Landed is extracting dates, conditions, and identifiers from each document, then reconciling them into one current status.
        </p>
      </div>
      <div ref={containerRef} className="mt-4 h-72 overflow-y-auto rounded-[24px] border border-border bg-white/85 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
        {lines.map((line, index) => (
          <motion.p
            key={`${line}-${index}`}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="font-mono text-xs leading-6 text-text-secondary"
          >
            {line}
          </motion.p>
        ))}
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
    </section>
  );
}
