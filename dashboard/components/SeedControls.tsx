"use client";

import { useState } from "react";
import {
  GraduationCap,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Waves,
  Zap,
} from "lucide-react";
import type { Seed } from "@/lib/api";
import { fmtUsd } from "@/lib/format";

interface Props {
  seeds: Seed[];
  busy: string | null;
  onRecover: (seedId: string) => void;
  onLearn: () => void;
  onDrift: (seedId: string) => void;
  onPlayDemo: () => void;
  onReset: () => void;
}

// One-click controls to fire each seed on camera, plus the learning and drift
// demo triggers, a hands-free "Play full demo", and a Reset for a clean board.
export default function SeedControls({
  seeds,
  busy,
  onRecover,
  onLearn,
  onDrift,
  onPlayDemo,
  onReset,
}: Props) {
  const [hover, setHover] = useState<string | null>(null);

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="section-title">
          <SlidersHorizontal className="h-4 w-4 text-accent" />
          Demo controls
        </h2>
        <div className="flex flex-wrap gap-2">
          <button
            className="btn btn-accent"
            disabled={busy !== null}
            onClick={onPlayDemo}
            title="Run the full storyboard hands-free (ideal for recording)"
          >
            <Play className="h-4 w-4" />
            {busy === "play" ? "Playing…" : "Play full demo"}
          </button>
          <button
            className="btn"
            disabled={busy !== null}
            onClick={onReset}
            title="Clear all runs, approvals, and memory for a fresh demo"
          >
            <RotateCcw className="h-4 w-4" />
            {busy === "reset" ? "Resetting…" : "Reset"}
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted">Manual steps:</span>
        <button
          className="btn"
          disabled={busy !== null}
          onClick={onLearn}
          title="Run experiment-gated promotion (episodic to distilled lessons)"
        >
          <GraduationCap className="h-4 w-4" />
          {busy === "learn" ? "Learning…" : "Run learning"}
        </button>
        <button
          className="btn"
          disabled={busy !== null}
          onClick={() => onDrift("C0")}
          title="Simulate a silent destination rule change, then auto-heal"
        >
          <Waves className="h-4 w-4" />
          {busy === "drift" ? "Detecting…" : "Trigger drift"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
        {seeds.map((s) => {
          const isWild = s.id === "W1";
          const isClean = s.expected_error === null;
          return (
            <button
              key={s.id}
              className={`group flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition
                ${
                  isWild
                    ? "border-veto/40 bg-veto/5 hover:border-veto"
                    : "border-edge bg-panel2 hover:border-accent/60"
                }
                disabled:cursor-not-allowed disabled:opacity-40`}
              disabled={busy !== null}
              onClick={() => onRecover(s.id)}
              onMouseEnter={() => setHover(s.id)}
              onMouseLeave={() => setHover(null)}
            >
              <div className="flex w-full items-center justify-between">
                <span className="flex items-center gap-1 font-mono text-sm font-semibold text-ink">
                  {s.id}
                  {isWild ? <Zap className="h-3.5 w-3.5 text-veto" /> : null}
                </span>
                <span className="text-xs text-muted">{fmtUsd(s.value)}</span>
              </div>
              <span className="text-xs text-muted">
                {busy === s.id
                  ? "Running…"
                  : s.expected_error
                    ? s.expected_error
                    : isClean
                      ? "clean control"
                      : "—"}
              </span>
              {hover === s.id && s.note ? (
                <span className="text-[11px] leading-tight text-faint">
                  {s.note}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
