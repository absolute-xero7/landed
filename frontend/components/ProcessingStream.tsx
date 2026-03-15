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
    <section className="w-full rounded-2xl border border-border bg-bg-surface p-6 shadow-sm">
      <h2 className="font-heading text-2xl text-text-primary">Reading your documents</h2>
      <div className="mt-4 overflow-hidden rounded bg-bg-raised">
        <div className="h-[3px] bg-canada-red/40" style={{ width: `${Math.max(progress, 5)}%`, transition: "width 350ms ease" }} />
      </div>
      <div ref={containerRef} className="mt-4 h-72 overflow-y-auto rounded-lg border border-border bg-white p-3">
        {lines.map((line, index) => (
          <motion.p
            key={`${line}-${index}`}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="font-mono text-xs text-text-secondary"
          >
            {line}
          </motion.p>
        ))}
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
    </section>
  );
}
