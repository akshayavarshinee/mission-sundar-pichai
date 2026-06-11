"use client";

import { useState } from "react";
import { AlertTriangle, FlaskConical, LineChart, Menu, X } from "lucide-react";
import { API_BASE, phoenixTraceUrl } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import Sidebar from "@/components/shell/Sidebar";
import DemoDrawer from "@/components/shell/DemoDrawer";
import DriftBanner from "@/components/DriftBanner";
import ThemeToggle from "@/components/ThemeToggle";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { health, connected, driftAlert, driftHealed, dismissDrift, error } = useWorkspace();
  const [mobileNav, setMobileNav] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const online = Boolean(health);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar */}
      {mobileNav ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileNav(false)} />
          <div className="absolute left-0 top-0 h-full">
            <Sidebar onNavigate={() => setMobileNav(false)} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-edge bg-bg/80 backdrop-blur supports-[backdrop-filter]:bg-bg/60">
          <div className="flex items-center justify-between gap-3 px-4 py-3 md:px-6">
            <div className="flex items-center gap-2">
              <button
                className="btn h-9 w-9 p-0 lg:hidden"
                onClick={() => setMobileNav((v) => !v)}
                aria-label="Toggle navigation"
              >
                {mobileNav ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span
                className="pill hidden border-edge text-muted sm:inline-flex"
                title={connected ? "event stream live" : "event stream reconnecting"}
              >
                <span className={`h-2 w-2 rounded-full ${connected ? "bg-good" : "bg-bad"}`} />
                {connected ? "live" : "offline"}
              </span>
              <span
                className={`pill ${
                  online ? "border-good/40 bg-good/10 text-good" : "border-bad/40 bg-bad/10 text-bad"
                }`}
                title={online ? `backend env: ${health?.env}` : "backend unreachable"}
              >
                <span className={`h-2 w-2 rounded-full ${online ? "bg-good" : "bg-bad"}`} />
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
              </a>

              <button className="btn h-9" onClick={() => setDemoOpen(true)}>
                <FlaskConical className="h-4 w-4" />
                <span className="hidden sm:inline">Demo</span>
              </button>

              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 md:p-6">
          {error ? (
            <div className="card flex items-start gap-2.5 border-bad/40 bg-bad/5 p-3 text-sm text-bad">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Backend error: {error}. Is the API running at{" "}
                <span className="font-mono">{API_BASE}</span>?
              </span>
            </div>
          ) : null}

          <DriftBanner alert={driftAlert} healed={driftHealed} onDismiss={dismissDrift} />

          {children}
        </main>
      </div>

      <DemoDrawer open={demoOpen} onClose={() => setDemoOpen(false)} />
    </div>
  );
}
