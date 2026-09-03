import React from "react";
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { pct } from "../../format";
import { C, ChartTable, TooltipBox, legendText, tick } from "./chartTheme";

function CalibrationTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  return (
    <TooltipBox
      title={`${b.label} · ${b.n} fights`}
      rows={[
        { label: "actual hit rate", value: pct(b.hit), color: C.accent },
        { label: "avg stated confidence", value: pct(b.stated), color: C.gray },
      ]}
    />
  );
}

export default function CalibrationChart({ bands }) {
  const data = bands.filter((b) => b.n > 0);
  return (
    <div>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={2} barCategoryGap="32%" margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="label" tick={tick} axisLine={{ stroke: C.grid }} tickLine={false} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={tick}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<CalibrationTooltip />} />
            <Legend iconType="rect" iconSize={10} formatter={legendText} />
            <Bar dataKey="stated" name="Stated confidence" fill={C.gray} barSize={20} radius={[4, 4, 0, 0]} />
            <Bar dataKey="hit" name="Actual hit rate" fill={C.accent} barSize={20} radius={[4, 4, 0, 0]}>
              <LabelList dataKey="hit" position="top" formatter={(v) => pct(v, 0)} style={{ fill: C.ink, fontSize: 12 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption="Calibration by confidence band"
        columns={["Band", "Fights", "Avg stated", "Actual hit rate"]}
        rows={bands.map((b) => [b.label, b.n, pct(b.stated), pct(b.hit)])}
      />
    </div>
  );
}
