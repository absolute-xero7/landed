"use client";

const LANGUAGES = [
  { code: "English", label: "English" },
  { code: "French", label: "French" },
  { code: "Hindi", label: "Hindi" },
  { code: "Punjabi", label: "Punjabi" },
  { code: "Tagalog", label: "Tagalog" },
  { code: "Mandarin", label: "Mandarin" },
  { code: "Arabic", label: "Arabic" },
  { code: "Spanish", label: "Spanish" },
];

interface LanguageSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export default function LanguageSelector({ value, onChange }: LanguageSelectorProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-text-secondary">
      Language
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-border bg-bg-surface px-2 py-1 text-text-primary focus:border-border-strong focus:outline-none"
      >
        {LANGUAGES.map((lang) => (
          <option value={lang.code} key={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </label>
  );
}
