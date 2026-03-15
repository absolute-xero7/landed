import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-base": "var(--bg-base)",
        "bg-surface": "var(--bg-surface)",
        "bg-raised": "var(--bg-raised)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-mono": "var(--text-mono)",
        "status-safe": "var(--status-safe)",
        "status-warn": "var(--status-warn)",
        "status-urgent": "var(--status-urgent)",
        "status-info": "var(--status-info)",
        "canada-red": "var(--canada-red)",
      },
      fontFamily: {
        heading: ["var(--font-fraunces)"],
        sans: ["var(--font-plex-sans)"],
        mono: ["var(--font-plex-mono)"],
      },
      keyframes: {
        subtlePulse: {
          "0%": { backgroundColor: "#ffffff" },
          "50%": { backgroundColor: "#fef2f2" },
          "100%": { backgroundColor: "#ffffff" },
        },
        streamProgress: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(0%)" },
        },
      },
      animation: {
        subtlePulse: "subtlePulse 3s ease-in-out infinite",
        streamProgress: "streamProgress 1.5s ease-out forwards",
      },
    },
  },
  plugins: [],
};

export default config;
