import { create } from "zustand";

import { ChatMessage, ExtractedDocument, ImmigrationProfile } from "@/lib/types";


interface SessionStore {
  sessionId: string | null;
  profile: ImmigrationProfile | null;
  documents: ExtractedDocument[];
  language: string;
  chatHistory: ChatMessage[];
  setSession: (id: string) => void;
  setProfile: (profile: ImmigrationProfile | null) => void;
  setDocuments: (docs: ExtractedDocument[]) => void;
  setLanguage: (language: string) => void;
  addMessage: (message: ChatMessage) => void;
  resetChat: () => void;
}


export const useSessionStore = create<SessionStore>((set) => ({
  sessionId: null,
  profile: null,
  documents: [],
  language: "English",
  chatHistory: [],
  setSession: (id) => set({ sessionId: id }),
  setProfile: (profile) => set({ profile }),
  setDocuments: (docs) => set({ documents: docs }),
  setLanguage: (language) => set({ language }),
  addMessage: (message) => set((state) => ({ chatHistory: [...state.chatHistory, message] })),
  resetChat: () => set({ chatHistory: [] }),
}));
