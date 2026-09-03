import React from "react";

/** label / value / sub. tone colors the value: "up" | "down" | undefined. */
export default function StatTile({ label, value, sub, tone }) {
  const toneClass = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";
  return (
    <div className="rounded-lg border border-hairline bg-surface px-5 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={`mt-1 font-body text-4xl font-semibold leading-none ${toneClass}`}>{value}</div>
      {sub && <div className="mt-2 text-sm text-ink-2">{sub}</div>}
    </div>
  );
}
