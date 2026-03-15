"use client";

import { motion } from "framer-motion";
import { Upload } from "lucide-react";
import { useMemo } from "react";
import { useDropzone } from "react-dropzone";

interface UploadZoneProps {
  files: File[];
  setFiles: (files: File[]) => void;
  onSubmit: () => void;
  submitting: boolean;
  error: string | null;
}

const MAX_FILES = 10;
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

export default function UploadZone({ files, setFiles, onSubmit, submitting, error }: UploadZoneProps) {
  const onDrop = (acceptedFiles: File[]) => {
    const combined = [...files, ...acceptedFiles].slice(0, MAX_FILES);
    setFiles(combined);
  };

  const dropzone = useDropzone({
    onDrop,
    maxFiles: MAX_FILES,
    maxSize: MAX_SIZE_BYTES,
    multiple: true,
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
  });

  const fileError = useMemo(() => {
    if (!dropzone.fileRejections.length) {
      return null;
    }
    return dropzone.fileRejections[0].errors[0]?.message ?? "Some files were rejected.";
  }, [dropzone.fileRejections]);

  return (
    <div className="w-full rounded-[28px] border border-border bg-[rgba(255,252,248,0.95)] p-5 shadow-[0_24px_80px_rgba(60,27,5,0.1)] backdrop-blur">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-text-secondary">Start a session</p>
          <h2 className="mt-1.5 font-heading text-[2rem] leading-[1.05] text-text-primary">Upload your immigration documents</h2>
        </div>
        <div className="rounded-full border border-border bg-white/80 px-3 py-1.5 font-mono text-xs uppercase tracking-[0.16em] text-text-secondary">
          Up to 10 files
        </div>
      </div>

      <div {...dropzone.getRootProps()}>
        <motion.div
          className={`cursor-pointer rounded-[24px] border border-dashed p-10 text-center transition-colors ${
            dropzone.isDragActive ? "border-canada-red bg-red-50/40" : "border-border bg-white/80"
          }`}
          whileHover={{ scale: 1.02 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
        >
          <input {...dropzone.getInputProps()} />
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-border bg-bg-raised shadow-[0_12px_30px_rgba(60,27,5,0.08)]">
            <Upload className="h-6 w-6 text-text-secondary" />
          </div>
          <p className="mt-4 text-lg text-text-primary">Drop immigration files here, or click to browse</p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-secondary">
            PDF, PNG, JPG, JPEG. Landed reads scanned documents, cross-references them, and explains what matters next.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs text-text-secondary">
            {["Study permits", "TRVs", "Passports", "Work permits", "IRCC letters"].map((item) => (
              <span key={item} className="rounded-full border border-border bg-bg-surface px-3 py-1.5">
                {item}
              </span>
            ))}
          </div>
        </motion.div>
      </div>

      {(error || fileError) && <p className="mt-3 text-sm text-red-700">{error || fileError}</p>}

      <div className="mt-4 max-h-64 space-y-2 overflow-y-auto pr-1">
        {files.map((file, index) => (
          <motion.div
            key={`${file.name}-${index}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="flex items-center justify-between rounded-2xl border border-border bg-white/80 px-4 py-2.5 shadow-[0_12px_24px_rgba(60,27,5,0.04)]"
          >
            <div>
              <p className="text-sm font-medium text-text-primary">{file.name}</p>
              <p className="mt-0.5 text-xs text-text-secondary">Ready to analyze</p>
            </div>
            <button
              type="button"
              onClick={() => setFiles(files.filter((_, i) => i !== index))}
              className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-wide text-text-secondary transition-colors hover:bg-bg-raised hover:text-text-primary"
            >
              Remove
            </button>
          </motion.div>
        ))}
      </div>

      <div className="sticky bottom-3 z-10 mt-4 rounded-[20px] bg-[linear-gradient(180deg,rgba(255,252,248,0),rgba(255,252,248,0.9)_28%,rgba(255,252,248,0.98))] px-1 pb-1 pt-5">
        <button
          type="button"
          onClick={onSubmit}
          disabled={files.length === 0 || submitting}
          className="w-full rounded-2xl bg-[linear-gradient(135deg,#cc0000,#9f1313)] px-5 py-3 text-sm font-medium text-white shadow-[0_22px_44px_rgba(159,19,19,0.24)] transition-transform transition-opacity hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Submitting..." : "Analyse Documents"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 rounded-[24px] border border-border bg-[linear-gradient(135deg,rgba(255,255,255,0.86),rgba(241,233,220,0.76))] p-3.5 text-sm text-text-secondary sm:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="font-medium text-text-primary">What you’ll get</p>
          <p className="mt-1 leading-6">A current-status summary, deadline timeline, work authorization details, risks, and grounded question answering.</p>
        </div>
        <div className="rounded-2xl border border-border bg-white/70 px-4 py-3">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-text-secondary">Privacy</p>
          <p className="mt-2 leading-6 text-text-primary">No account required. Files stay in memory for the current session and are cleared automatically.</p>
        </div>
      </div>
    </div>
  );
}
