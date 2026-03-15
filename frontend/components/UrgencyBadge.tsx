"use client";

interface UrgencyBadgeProps {
  urgency: "urgent" | "upcoming" | "future" | "critical" | "normal";
}

const styles: Record<UrgencyBadgeProps["urgency"], string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  urgent: "bg-red-50 text-red-700 border-red-200",
  upcoming: "bg-amber-50 text-amber-700 border-amber-200",
  future: "bg-blue-50 text-blue-700 border-blue-200",
  normal: "bg-green-50 text-green-700 border-green-200",
};

export default function UrgencyBadge({ urgency }: UrgencyBadgeProps) {
  return (
    <span className={`inline-flex rounded-full border px-2 py-1 font-mono text-xs uppercase tracking-wide ${styles[urgency]}`}>
      {urgency}
    </span>
  );
}
