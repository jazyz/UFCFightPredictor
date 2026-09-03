import React from "react";

// Series colors validated on the #151517 surface: accent carries the model,
// the neutral gray is de-emphasis context (the "emphasis" form, not a second hue).
export const C = {
  accent: "#e8362b",
  gray: "#b8b6ae",
  grid: "rgba(255,255,255,0.10)",
  axis: "#7c7a72",
  surface: "#151517",
  ink: "#f4f3ef",
  ink2: "#b8b6ae",
};

export const tick = { fill: C.axis, fontSize: 12, fontFamily: "Barlow, system-ui, sans-serif" };

/** Tooltip body: value first (strong), label second, keyed by a short line of the series color. */
export function TooltipBox({ title, rows }) {
  return (
    <div className="rounded-md border border-hairline bg-ground px-3 py-2 text-sm shadow-lg">
      <div className="mb-1 text-xs text-muted">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          {r.color && <span className="inline-block h-0.5 w-3" style={{ background: r.color }} />}
          <span className="tnum font-semibold text-ink">{r.value}</span>
          <span className="text-ink-2">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Every chart's table twin, collapsed behind a disclosure. */
export function ChartTable({ caption, columns, rows }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-muted hover:text-ink-2">View as table</summary>
      <table className="tnum mt-2 w-full text-left" aria-label={caption}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} className="border-b border-hairline py-1 pr-4 text-xs font-semibold uppercase tracking-wider text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((cell, j) => (
                <td key={j} className="border-b border-hairline py-1 pr-4 text-ink-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export const legendText = (value) => <span style={{ color: C.ink2, fontSize: 12 }}>{value}</span>;
