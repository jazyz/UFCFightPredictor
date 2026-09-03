import React from "react";
import {
  Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { monthLabel, pct } from "../../format";
import { C, ChartTable, TooltipBox, tick } from "./chartTheme";

function MonthTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <TooltipBox
      title={`${m.label} · ${m.n} fights`}
      rows={[{ label: "hit rate", value: pct(m.hit), color: C.accent }]}
    />
  );
}

export default function MonthlyAccuracyChart({ monthly, overall }) {
  const data = monthly.map((m) => ({ ...m, label: monthLabel(m.month) }));
  return (
    <div>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="35%" margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="label" tick={tick} axisLine={{ stroke: C.grid }} tickLine={false} interval={data.length > 14 ? "preserveStartEnd" : 0} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={tick}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<MonthTooltip />} />
            <ReferenceLine y={overall} stroke={C.gray} strokeWidth={1} />
            <Bar dataKey="hit" fill={C.accent} barSize={20} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption="Accuracy by month"
        columns={["Month", "Fights", "Hit rate"]}
        rows={data.map((m) => [m.label, m.n, pct(m.hit)])}
      />
    </div>
  );
}
