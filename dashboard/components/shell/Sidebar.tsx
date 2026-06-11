"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Anchor, FilePlus2, Inbox, LayoutGrid, Sparkles } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV: NavItem[] = [
  { href: "/", label: "Shipments", icon: LayoutGrid },
  { href: "/inbox", label: "Needs you", icon: Inbox },
  { href: "/submit", label: "New shipment", icon: FilePlus2 },
  { href: "/intelligence", label: "Intelligence", icon: Sparkles },
];

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { approvals } = useWorkspace();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-edge bg-panel">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <Anchor className="h-5 w-5" />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-ink">ClearPort</div>
          <div className="text-[11px] text-muted">Customs recovery</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          const showBadge = href === "/inbox" && approvals.length > 0;
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-accent/10 text-accent"
                  : "text-body hover:bg-panel2 hover:text-ink"
              }`}
            >
              <Icon className={`h-4 w-4 ${active ? "text-accent" : "text-muted group-hover:text-ink"}`} />
              <span className="flex-1">{label}</span>
              {showBadge ? (
                <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-warn/20 px-1.5 text-[11px] font-semibold text-warn">
                  {approvals.length}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-edge px-4 py-3 text-[11px] leading-relaxed text-faint">
        Gemini 3 · Google ADK · Arize Phoenix
        <br />
        EasyPost test mode
      </div>
    </aside>
  );
}
