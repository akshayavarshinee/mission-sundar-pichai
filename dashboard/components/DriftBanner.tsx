"use client";

import type { ClearEvent } from "@/lib/useEvents";

// A dismissible banner that lights up when the most recent drift_alert fires,
// then shows that the loop auto-healed the silent schema change.
export default function DriftBanner({
  alert,
  healed,
  onDismiss,
}: {
  alert: ClearEvent | null;
  healed: boolean;
  onDismiss: () => void;
}) {
  if (!alert) return null;
  const d = alert.data as Record<string, unknown>;

  return (
    <div
      className={`card flex items-center justify-between gap-4 border-l-4 p-4 ${
        healed ? "border-l-good bg-good/5" : "border-l-bad bg-bad/5"
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{healed ? "✅" : "⚠️"}</span>
        <div>
          <div className="text-sm font-semibold text-slate-100">
            {healed
              ? "Drift auto-healed"
              : "Destination rule changed — drift detected"}
          </div>
          <div className="text-xs text-slate-400">
            {String(d.rule ?? "Silent schema change")} · pass-rate{" "}
            <span className="text-bad">{String(d.pass_rate ?? "?")}</span> &lt; floor{" "}
            {String(d.floor ?? "?")}
            {healed
              ? " — agent re-investigated and re-promoted a fix."
              : " — re-investigating…"}
          </div>
        </div>
      </div>
      <button className="btn" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}
