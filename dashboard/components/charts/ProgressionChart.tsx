"use client";

import type { ProgressionPoint } from "@/lib/api";
import { fmtSeconds, fmtTime } from "@/lib/format";

// The headline visual: a dual-axis, hand-rolled SVG chart (no chart library).
//   • Left axis (area + line, sky):  cumulative auto-resolve %  — "gets smarter"
//   • Right axis (dashed step, violet): cumulative lessons learned
//   • Per-run dots coloured by outcome, with a violet ring when self-healed.
//   • Dashed verticals mark the runs where new lessons were promoted.
// Everything is plotted against the real run index (timestamps live in hovers).

const W = 760;
const H = 280;
const PAD_L = 42;
const PAD_R = 40;
const PAD_T = 22;
const PAD_B = 30;
const INNER_W = W - PAD_L - PAD_R;
const INNER_H = H - PAD_T - PAD_B;

// Outcome → dot colour (inherited via currentColor).
function dotClass(status: string): string {
  switch (status) {
    case "AUTO_RESOLVED":
      return "text-good";
    case "HUMAN_APPROVED":
      return "text-accent";
    case "HUMAN_CORRECTED":
      return "text-warn";
    case "REJECTED":
    case "HUMAN_REJECTED":
      return "text-bad";
    default:
      return "text-faint";
  }
}

export default function ProgressionChart({ points }: { points: ProgressionPoint[] }) {
  if (points.length === 0) return null;
  const n = points.length;
  const maxLessons = Math.max(1, ...points.map((p) => p.cum_lessons));

  const x = (i: number) => (n === 1 ? PAD_L + INNER_W / 2 : PAD_L + (i / (n - 1)) * INNER_W);
  const yPct = (v: number) => PAD_T + INNER_H * (1 - Math.max(0, Math.min(100, v)) / 100);
  const yLes = (v: number) => PAD_T + INNER_H * (1 - v / maxLessons);

  // Auto-resolve % — line + filled area down to the baseline.
  const linePts = points.map((p, i) => `${x(i).toFixed(1)},${yPct(p.cum_auto_pct).toFixed(1)}`);
  const linePath = `M ${linePts.join(" L ")}`;
  const areaPath = `M ${x(0).toFixed(1)},${yPct(0).toFixed(1)} L ${linePts.join(
    " L "
  )} L ${x(n - 1).toFixed(1)},${yPct(0).toFixed(1)} Z`;

  // Cumulative lessons — a stepped line (hold, then jump).
  const stepCmds: string[] = [];
  points.forEach((p, i) => {
    const px = x(i).toFixed(1);
    const py = yLes(p.cum_lessons).toFixed(1);
    if (i === 0) {
      stepCmds.push(`M ${px},${py}`);
    } else {
      const prevY = yLes(points[i - 1].cum_lessons).toFixed(1);
      stepCmds.push(`L ${px},${prevY} L ${px},${py}`);
    }
  });
  const stepPath = stepCmds.join(" ");

  // Where new lessons were promoted (cum_lessons increased).
  const promotions = points
    .map((p, i) => ({ p, i, delta: p.cum_lessons - (i === 0 ? 0 : points[i - 1].cum_lessons) }))
    .filter((m) => m.delta > 0);

  const ticks = Array.from(new Set([0, Math.floor((n - 1) / 2), n - 1]));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Cumulative auto-resolve rate and lessons learned over time"
    >
      {/* horizontal gridlines + left axis labels */}
      {[0, 25, 50, 75, 100].map((g) => (
        <g key={g} className="text-edge">
          <line
            x1={PAD_L}
            y1={yPct(g)}
            x2={W - PAD_R}
            y2={yPct(g)}
            stroke="currentColor"
            strokeWidth={1}
            strokeDasharray={g === 0 ? undefined : "3 5"}
          />
          <text
            x={PAD_L - 7}
            y={yPct(g) + 3.5}
            textAnchor="end"
            fill="currentColor"
            className="text-faint"
            fontSize={10}
          >
            {g}%
          </text>
        </g>
      ))}

      {/* right axis (lessons) end labels */}
      <text x={W - PAD_R + 7} y={yLes(maxLessons) + 3.5} fill="currentColor" className="text-veto" fontSize={10}>
        {maxLessons}
      </text>
      <text x={W - PAD_R + 7} y={yLes(0) + 3.5} fill="currentColor" className="text-veto" fontSize={10}>
        0
      </text>

      {/* lesson-promotion markers */}
      {promotions.map((m) => (
        <g key={`promo-${m.i}`} className="text-veto">
          <line
            x1={x(m.i)}
            y1={PAD_T}
            x2={x(m.i)}
            y2={PAD_T + INNER_H}
            stroke="currentColor"
            strokeWidth={1}
            strokeDasharray="4 4"
            className="text-veto/50"
          />
          <text x={x(m.i) + 4} y={PAD_T + 2} fill="currentColor" className="text-veto" fontSize={10} fontWeight={600}>
            +{m.delta}
          </text>
        </g>
      ))}

      {/* auto-resolve area + line */}
      <path d={areaPath} fill="currentColor" className="text-accent/10" />
      <path
        d={linePath}
        fill="none"
        stroke="currentColor"
        className="text-accent"
        strokeWidth={2.5}
        strokeLinejoin="round"
      />

      {/* cumulative lessons (stepped, dashed) */}
      <path
        d={stepPath}
        fill="none"
        stroke="currentColor"
        className="text-veto"
        strokeWidth={2}
        strokeDasharray="5 4"
        strokeLinejoin="round"
      />

      {/* per-run dots */}
      {points.map((p, i) => (
        <g key={p.run_id}>
          {p.self_healed ? (
            <circle
              cx={x(i)}
              cy={yPct(p.cum_auto_pct)}
              r={5.5}
              fill="none"
              stroke="currentColor"
              className="text-veto"
              strokeWidth={2}
            />
          ) : null}
          <circle cx={x(i)} cy={yPct(p.cum_auto_pct)} r={3.2} fill="currentColor" className={dotClass(p.status)}>
            <title>
              {`Run ${p.index} · ${fmtTime(p.created_at)}\n${p.error_type} → ${p.status}\n` +
                `${p.cum_auto_pct.toFixed(0)}% auto-resolved · ${p.cum_lessons} lesson(s) known\n` +
                `recovered in ${fmtSeconds(p.recovery_seconds)}${p.self_healed ? " · self-healed from memory" : ""}`}
            </title>
          </circle>
        </g>
      ))}

      {/* final auto-resolve value callout */}
      <text
        x={x(n - 1)}
        y={Math.max(PAD_T + 10, yPct(points[n - 1].cum_auto_pct) - 9)}
        textAnchor="end"
        fill="currentColor"
        className="text-accent"
        fontSize={12}
        fontWeight={700}
      >
        {points[n - 1].cum_auto_pct.toFixed(0)}% auto
      </text>

      {/* x-axis run labels */}
      {ticks.map((ti) => (
        <text
          key={ti}
          x={x(ti)}
          y={H - 9}
          textAnchor={ti === 0 ? "start" : ti === n - 1 ? "end" : "middle"}
          fill="currentColor"
          className="text-faint"
          fontSize={10}
        >
          Run {points[ti].index}
        </text>
      ))}
    </svg>
  );
}
