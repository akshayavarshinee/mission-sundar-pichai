"use client";

// A hand-rolled SVG donut (no chart dependency). Renders a single ratio as a
// rounded value arc over a faint track, with a two-line label in the center.
// Colours are passed as text-* classes and inherited via `currentColor`, so the
// component stays in lockstep with the CSS-var theme (light/dark).
export default function Donut({
  ratio,
  size = 128,
  thickness = 14,
  valueClass = "text-good",
  trackClass = "text-bad/20",
  centerValue,
  centerLabel,
}: {
  ratio: number; // 0..1
  size?: number;
  thickness?: number;
  valueClass?: string;
  trackClass?: string;
  centerValue: string;
  centerLabel?: string;
}) {
  const r = (size - thickness) / 2;
  const circ = 2 * Math.PI * r;
  const safe = Number.isFinite(ratio) ? ratio : 0;
  const clamped = Math.max(0, Math.min(1, safe));
  const filled = circ * clamped;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${centerValue} ${centerLabel ?? ""}`.trim()}
    >
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`} fill="none" strokeLinecap="round">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={thickness}
          stroke="currentColor"
          className={trackClass}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={thickness}
          stroke="currentColor"
          className={valueClass}
          strokeDasharray={`${filled} ${circ - filled}`}
        />
      </g>
      <text
        x="50%"
        y={centerLabel ? "46%" : "50%"}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="currentColor"
        className="text-ink"
        fontSize={size * 0.24}
        fontWeight={700}
      >
        {centerValue}
      </text>
      {centerLabel ? (
        <text
          x="50%"
          y="64%"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="currentColor"
          className="text-muted"
          fontSize={size * 0.1}
        >
          {centerLabel}
        </text>
      ) : null}
    </svg>
  );
}
