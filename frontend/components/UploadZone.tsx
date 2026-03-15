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
    <div className="w-full rounded-2xl border border-border bg-bg-surface p-6 shadow-sm">
      <div {...dropzone.getRootProps()}>
        <motion.div
          className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            dropzone.isDragActive ? "border-canada-red" : "border-border"
          }`}
          whileHover={{ scale: 1.02 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
        >
          <input {...dropzone.getInputProps()} />
          <div className="flex items-center justify-center gap-3">
            <Upload className="h-5 w-5 text-text-secondary" />
            <p className="text-base text-text-primary">Drop immigration files here, or click to browse</p>
          </div>
          <p className="mt-2 text-sm text-text-secondary">PDF, PNG, JPG, JPEG. Max 10 files, 10MB each.</p>
        </motion.div>
      </div>

      {(error || fileError) && <p className="mt-3 text-sm text-red-700">{error || fileError}</p>}

      <div className="mt-4 space-y-2">
        {files.map((file, index) => (
          <motion.div
            key={`${file.name}-${index}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
          >
            <span className="text-sm text-text-primary">{file.name}</span>
            <button
              type="button"
              onClick={() => setFiles(files.filter((_, i) => i !== index))}
              className="text-sm text-text-secondary hover:text-text-primary"
            >
              x
            </button>
          </motion.div>
        ))}
      </div>

      <button
        type="button"
        onClick={onSubmit}
        disabled={files.length === 0 || submitting}
        className="mt-5 w-full rounded-lg bg-text-primary px-4 py-2 text-bg-surface transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
      >
        {submitting ? "Submitting..." : "Analyse Documents"}
      </button>
    </div>
  );
}
