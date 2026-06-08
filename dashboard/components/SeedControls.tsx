"use client";

import { useState } from "react";
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
        <h2 className="text-sm font-semibold text-slate-200">Demo controls</h2>
        <div className="flex flex-wrap gap-2">
          <button
            className="btn btn-accent"
            disabled={busy !== null}
            onClick={onPlayDemo}
            title="Run the full storyboard hands-free (ideal for recording)"
          >
            {busy === "play" ? "Playing…" : "▶ Play full demo"}
          </button>
          <button
            className="btn"
            disabled={busy !== null}
            onClick={onReset}
            title="Clear all runs, approvals, and memory for a fresh demo"
          >
            {busy === "reset" ? "Resetting…" : "Reset"}
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500">Manual steps:</span>
        <button
          className="btn"
          disabled={busy !== null}
          onClick={onLearn}
          title="Run experiment-gated promotion (episodic ② → distilled ③)"
        >
          {busy === "learn" ? "Learning…" : "Run learning"}
        </button>
        <button
          className="btn"
          disabled={busy !== null}
          onClick={() => onDrift("C0")}
          title="Simulate a silent destination rule change, then auto-heal"
        >
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
                    ? "border-veto/50 bg-veto/5 hover:border-veto"
                    : "border-edge bg-panel2 hover:border-accent"
                }
                disabled:cursor-not-allowed disabled:opacity-40`}
              disabled={busy !== null}
              onClick={() => onRecover(s.id)}
              onMouseEnter={() => setHover(s.id)}
              onMouseLeave={() => setHover(null)}
            >
              <div className="flex w-full items-center justify-between">
                <span className="font-mono text-sm font-semibold text-white">
                  {s.id}
                  {isWild ? " ⚡" : ""}
                </span>
                <span className="text-xs text-slate-400">{fmtUsd(s.value)}</span>
              </div>
              <span className="text-xs text-slate-400">
                {busy === s.id
                  ? "Running…"
                  : s.expected_error
                    ? s.expected_error
                    : isClean
                      ? "clean control"
                      : "—"}
              </span>
              {hover === s.id && s.note ? (
                <span className="text-[11px] leading-tight text-slate-500">
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
