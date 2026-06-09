"use client";

import { Anchor, CircleDot, ExternalLink, LineChart, Sparkles } from "lucide-react";
import type { Health } from "@/lib/api";
import { phoenixTraceUrl } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";

interface Props {
  health: Health | null;
  agentBuilderUrl: string;
  connected: boolean;
}

// Sticky top bar: brand identity, live backend + event-stream status, external
// deep-links, and the theme switch.
export default function Topbar({ health, agentBuilderUrl, connected }: Props) {
  const online = Boolean(health);

  return (
    <header className="sticky top-0 z-20 border-b border-edge bg-bg/80 backdrop-blur supports-[backdrop-filter]:bg-bg/60">
      <div className="flex items-center justify-between gap-4 px-4 py-3 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Anchor className="h-5 w-5" />
          </span>
          <div className="min-w-0 leading-tight">
            <h1 className="truncate text-base font-semibold tracking-tight text-ink">
              ClearPort
              <span className="ml-2 hidden text-xs font-normal text-muted sm:inline">
                Customs Recovery Console
              </span>
            </h1>
            <p className="hidden truncate text-xs text-muted md:block">
              Arize eval-gate · human approvals · experiment-gated learning ·
              drift detection
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="pill hidden border-edge text-muted lg:inline-flex"
            title={connected ? "event stream live" : "event stream reconnecting"}
          >
            <CircleDot
              className={`h-3.5 w-3.5 ${connected ? "text-good" : "text-bad"}`}
            />
            {connected ? "live" : "offline"}
          </span>

          <span
            className={`pill ${
              online
                ? "border-good/40 bg-good/10 text-good"
                : "border-bad/40 bg-bad/10 text-bad"
            }`}
            title={online ? `backend env: ${health?.env}` : "backend unreachable"}
          >
            <span
              className={`h-2 w-2 rounded-full ${online ? "bg-good" : "bg-bad"}`}
            />
            <span className="hidden sm:inline">backend</span>
            {online ? `: ${health?.env}` : " down"}
          </span>

          <a
            className="btn hidden h-9 sm:inline-flex"
            href={phoenixTraceUrl()}
            target="_blank"
            rel="noreferrer"
          >
            <LineChart className="h-4 w-4" />
            <span className="hidden md:inline">Phoenix</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-60" />
          </a>

          <a
            className="btn hidden h-9 sm:inline-flex"
            href={agentBuilderUrl}
            target="_blank"
            rel="noreferrer"
          >
            <Sparkles className="h-4 w-4" />
            <span className="hidden md:inline">Agent Builder</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-60" />
          </a>

          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
