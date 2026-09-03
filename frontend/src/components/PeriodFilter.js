import React from "react";
import { useSearchParams } from "react-router-dom";
import { presets } from "../aggregate";

/** One filter row above the results: presets plus a custom range, mirrored in the URL. */
export default function PeriodFilter({ range, window: win }) {
  const [, setParams] = useSearchParams();
  const set = (from, to) => setParams(from === range.start && to === range.end ? {} : { from, to });
  const input = "rounded-md border border-hairline bg-surface px-2 py-1 text-sm text-ink";
  return (
    <div className="mx-auto max-w-content px-6 pt-6" role="group" aria-label="Time period">
      <div className="flex flex-wrap items-center gap-2">
        {presets(range).map(([label, s, e]) => {
          const active = s === win.start && e === win.end;
          return (
            <button
              key={label}
              type="button"
              aria-pressed={active}
              onClick={() => set(s, e)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                active ? "border-ink bg-surface text-ink" : "border-hairline text-ink-2 hover:text-ink"
              }`}
            >
              {label}
            </button>
          );
        })}
        <label className="ml-2 flex items-center gap-2 text-sm text-ink-2">
          From
          <input type="date" aria-label="From date" className={input} min={range.start} max={win.end} value={win.start}
            onChange={(e) => e.target.value && set(e.target.value, win.end)} />
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          to
          <input type="date" aria-label="To date" className={input} min={win.start} max={range.end} value={win.end}
            onChange={(e) => e.target.value && set(win.start, e.target.value)} />
        </label>
      </div>
    </div>
  );
}
