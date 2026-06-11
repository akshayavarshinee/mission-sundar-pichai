"use client";

import { useRouter } from "next/navigation";
import {
  Database,
  GraduationCap,
  Play,
  RotateCcw,
  Waves,
  X,
  Zap,
} from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { fmtUsd } from "@/lib/format";
import { errorLabel } from "@/lib/shipment";

// Stage controls for demos & judging — deliberately kept out of the main product
// surface and tucked into this slide-over so the app reads as a product.
export default function DemoDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const { seeds, busy, recover, learn, drift, playDemo, seedHistory, reset } = useWorkspace();

  const fireSeed = async (seedId: string) => {
    const run = await recover(seedId);
    if (run) {
      onClose();
      router.push(`/shipments/${run.run_id}`);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-40 ${open ? "" : "pointer-events-none"}`}
      aria-hidden={!open}
    >
      <div
        className={`absolute inset-0 bg-black/40 transition-opacity ${
          open ? "opacity-100" : "opacity-0"
        }`}
        onClick={onClose}
      />
      <div
        className={`absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-edge bg-panel shadow-xl transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-edge px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Demo & sandbox</h2>
            <p className="text-xs text-muted">Stage scenarios for a walkthrough.</p>
          </div>
          <button className="btn h-9 w-9 p-0" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-accent" disabled={busy !== null} onClick={playDemo}>
              <Play className="h-4 w-4" />
              {busy === "play" ? "Playing…" : "Play full demo"}
            </button>
            <button className="btn" disabled={busy !== null} onClick={reset}>
              <RotateCcw className="h-4 w-4" />
              {busy === "reset" ? "Resetting…" : "Reset board"}
            </button>
          </div>

          <div className="rounded-lg border border-edge bg-panel2 p-3">
            <button
              className="btn btn-accent w-full"
              disabled={busy !== null}
              onClick={seedHistory}
            >
              <Database className="h-4 w-4" />
              {busy === "seed" ? "Building learning history…" : "Seed rich history"}
            </button>
            <p className="mt-2 text-[11px] leading-relaxed text-faint">
              Runs ~24 real recoveries — cold-start escalations, human corrections, promoted
              lessons, then self-heals from memory — so the Intelligence page shows learning
              over time. Resets the board first.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button className="btn" disabled={busy !== null} onClick={learn}>
              <GraduationCap className="h-4 w-4" />
              {busy === "learn" ? "Learning…" : "Run learning"}
            </button>
            <button className="btn" disabled={busy !== null} onClick={() => drift("C0")}>
              <Waves className="h-4 w-4" />
              {busy === "drift" ? "Detecting…" : "Trigger drift"}
            </button>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-faint">
              Example shipments
            </div>
            <div className="grid grid-cols-1 gap-2">
              {seeds.map((s) => {
                const isWild = s.id === "W1";
                return (
                  <button
                    key={s.id}
                    className={`flex items-center justify-between gap-3 rounded-lg border p-3 text-left transition disabled:opacity-40 ${
                      isWild
                        ? "border-veto/40 bg-veto/5 hover:border-veto"
                        : "border-edge bg-panel2 hover:border-accent/60"
                    }`}
                    disabled={busy !== null}
                    onClick={() => fireSeed(s.id)}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-sm font-medium text-ink">
                        {s.persona.split(" ").slice(0, 4).join(" ")}
                        {isWild ? <Zap className="h-3.5 w-3.5 text-veto" /> : null}
                      </div>
                      <div className="truncate text-xs text-muted">
                        {s.expected_error ? errorLabel(s.expected_error) : "Clean control"}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="font-mono text-xs text-muted">{s.id}</div>
                      <div className="text-xs text-faint">{fmtUsd(s.value)}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
