"use client";

import { AnimatePresence, motion } from "framer-motion";
import { MessageCircle } from "lucide-react";
import { useState } from "react";

import ChatQA from "@/components/ChatQA";

interface ChatLauncherProps {
  sessionId: string;
  language: string;
  onLanguageChange: (value: string) => void;
}

export default function ChatLauncher({ sessionId, language, onLanguageChange }: ChatLauncherProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="fixed bottom-[88px] right-6 z-40 w-[min(440px,calc(100vw-2rem))]"
          >
            <ChatQA sessionId={sessionId} language={language} onLanguageChange={onLanguageChange} />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={() => setOpen((current) => !current)}
        whileTap={{ scale: 0.97 }}
        className="fixed bottom-6 right-6 z-50 inline-flex max-w-[160px] items-center justify-center gap-2 rounded-full border border-[rgba(204,0,0,0.16)] bg-[linear-gradient(135deg,#cc0000,#9f1313)] px-4 py-2.5 text-sm font-medium text-white shadow-[0_20px_50px_rgba(159,19,19,0.32)]"
      >
        <MessageCircle className="h-5 w-5" />
        <span>Ask</span>
      </motion.button>
    </>
  );
}
