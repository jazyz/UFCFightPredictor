import React from "react";
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { eventName, money, monthLabel, shortDate } from "../../format";
import { C, ChartTable, TooltipBox, tick } from "./chartTheme";

function BankrollTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const title = d.event === "start" ? "Start" : `${shortDate(d.date)} · ${eventName(d.event)}`;
  return <TooltipBox title={title} rows={[{ label: "bankroll", value: money(d.bankroll), color: C.accent }]} />;
}

/** Month-end checkpoints for the table twin. */
function monthEnds(points) {
  const last = new Map();
  points.forEach((p) => last.set(p.date.slice(0, 7), p.bankroll));
  return [...last.entries()].map(([m, b]) => [monthLabel(m), money(b)]);
}

export default function BankrollChart({ points, start = 1000 }) {
  const data = [
    { i: 0, date: points[0]?.date ?? "", event: "start", bankroll: start },
    ...points.map((p, k) => ({ i: k + 1, ...p })),
  ];
  const ticks = [];
  let seen = null;
  data.slice(1).forEach((d) => {
    const m = d.date.slice(0, 7);
    if (m !== seen) {
      ticks.push(d.i);
      seen = m;
    }
  });
  const values = data.map((d) => d.bankroll);
  const lo = Math.floor(Math.min(...values) / 50) * 50;
  const hi = Math.ceil(Math.max(...values) / 50) * 50;
  return (
    <div>
      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="bankrollWash" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.accent} stopOpacity={0.18} />
                <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis
              dataKey="i"
              type="number"
              domain={[0, data.length - 1]}
              ticks={ticks}
              tickFormatter={(i) => monthLabel(data[i].date.slice(0, 7))}
              tick={tick}
              axisLine={{ stroke: C.grid }}
              tickLine={false}
            />
            <YAxis
              domain={[lo, hi]}
              tickFormatter={(v) => `$${v.toLocaleString("en-US")}`}
              tick={tick}
              axisLine={false}
              tickLine={false}
              width={72}
            />
            <ReferenceLine
              y={start}
              stroke={C.gray}
              strokeWidth={1}
              label={{ value: "break-even", position: "insideBottomRight", fill: C.ink2, fontSize: 12 }}
            />
            <Tooltip cursor={{ stroke: C.gray, strokeWidth: 1 }} content={<BankrollTooltip />} />
            <Area
              type="linear"
              dataKey="bankroll"
              stroke={C.accent}
              strokeWidth={2}
              fill="url(#bankrollWash)"
              dot={false}
              activeDot={{ r: 4, fill: C.accent, stroke: C.surface, strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ChartTable caption="Bankroll at month end" columns={["Month", "Bankroll"]} rows={monthEnds(points)} />
    </div>
  );
}
