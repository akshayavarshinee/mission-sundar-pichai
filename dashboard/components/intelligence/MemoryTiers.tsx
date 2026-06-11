"use client";

import { Database } from "lucide-react";
import type { MemoryIntel, TierUsage } from "@/lib/api";

// Four-tier long-term memory at a glance. Each tier is coloured to read as a
// distinct "shelf": ① law (violet, vetoes) · ② episodic (sky, the record) ·
// ③ lessons (emerald, what works) · ④ prompts (amber, how to reason).
const TONES = [
  { ring: "border-veto/40 bg-veto/10 text-veto", value: "text-veto" },
  { ring: "border-accent/40 bg-accent/10 text-accent", value: "text-accent" },
  { ring: "border-good/40 bg-good/10 text-good", value: "text-good" },
  { ring: "border-warn/40 bg-warn/10 text-warn", value: "text-warn" },
];

export default function MemoryTiers({ memory }: { memory: MemoryIntel }) {
  return (
    <section className="card p-5">
      <h2 className="section-title">
        <Database className="h-4 w-4 text-accent" />
        Long-term memory — four tiers
      </h2>
      <p className="mt-1 text-xs text-muted">
        Law grounds and vetoes · episodic records every outcome · lessons distill what works ·
        prompts version the reasoning.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {memory.tiers.map((tier, i) => (
          <TierCard key={tier.tier} tier={tier} tone={TONES[i % TONES.length]} />
        ))}
      </div>
    </section>
  );
}

function TierCard({
  tier,
  tone,
}: {
  tier: TierUsage;
  tone: { ring: string; value: string };
}) {
  return (
    <div className="flex flex-col rounded-lg border border-edge bg-panel2 p-3">
      <div className="flex items-center gap-2">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${tone.ring}`}
        >
          {tier.tier}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-ink">{tier.name}</div>
          <div className="truncate font-mono text-[11px] text-faint">{tier.backend}</div>
        </div>
      </div>
      <div className={`mt-2 text-2xl font-semibold tabular-nums ${tone.value}`}>{tier.count}</div>
      <p className="mt-1 flex-1 text-[11px] leading-relaxed text-muted">{tier.purpose}</p>
      <div className="mt-2 flex flex-wrap gap-1">
        {tier.detail.map((d, k) => (
          <span
            key={k}
            className="rounded-full border border-edge bg-panel px-2 py-0.5 text-[10px] text-muted"
          >
            {d}
          </span>
        ))}
      </div>
    </div>
  );
}
