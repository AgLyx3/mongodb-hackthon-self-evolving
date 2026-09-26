"use client";

import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Point = { label: string; acc: number };
type AccuracyChartProps = {
  points: Point[];
  noisePts: number;
  strongBaseline: number | null;
};

export function AccuracyChart({ points, noisePts, strongBaseline }: AccuracyChartProps) {
  const data = points.map((p) => ({
    label: p.label,
    acc: Math.round(p.acc * 1000) / 10,
    band: [
      Math.max(0, Math.round(p.acc * 1000) / 10 - noisePts),
      Math.min(100, Math.round(p.acc * 1000) / 10 + noisePts),
    ],
  }));
  return (
    <div
      style={{ height: 260, width: "100%" }}
      role="img"
      aria-label="Holdout accuracy by harness version, with noise band"
    >
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <XAxis dataKey="label" stroke="var(--color-content-muted)" fontSize={12} />
          <YAxis domain={[0, 100]} unit="%" stroke="var(--color-content-muted)" fontSize={12} />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface-raised)",
              border: "1px solid var(--color-border)",
              color: "var(--color-content)",
            }}
          />
          <Area
            dataKey="band"
            stroke="none"
            fill="var(--color-neutral-hover)"
            name="noise band"
            isAnimationActive={false}
          />
          <Line
            dataKey="acc"
            type="stepAfter"
            stroke="var(--color-primary)"
            strokeWidth={2}
            dot
            name="holdout accuracy %"
            isAnimationActive={false}
          />
          {strongBaseline !== null ? (
            <ReferenceLine
              y={Math.round(strongBaseline * 1000) / 10}
              stroke="var(--color-warning)"
              strokeDasharray="4 4"
              label={{
                value: "strong model, base harness",
                fill: "var(--color-content-muted)",
                fontSize: 12,
                position: "insideTopRight",
              }}
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
