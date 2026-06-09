// Small presentation helpers shared across components.

export function fmtUsd(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export function fmtSeconds(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n < 1) return `${(n * 1000).toFixed(0)} ms`;
  if (n < 60) return `${n.toFixed(1)} s`;
  const m = Math.floor(n / 60);
  return `${m}m ${Math.round(n % 60)}s`;
}

export function fmtDays(seconds: number): string {
  const days = seconds / 86400;
  return days >= 1 ? `${days.toFixed(1)} d` : fmtSeconds(seconds);
}

export function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-US", { hour12: false });
  } catch {
    return iso;
  }
}

export function pct(n: number): string {
  return `${n.toFixed(0)}%`;
}

// Map a decision/status to a semantic colour class.
export function decisionTone(decision: string): string {
  switch (decision.toUpperCase()) {
    case "AUTO":
    case "AUTO_RESOLVED":
    case "HUMAN_APPROVED":
    case "HUMAN_CORRECTED":
      return "text-good";
    case "ESCALATE":
    case "AWAITING_APPROVAL":
      return "text-warn";
    case "BLOCK":
    case "REJECTED":
    case "HUMAN_REJECTED":
      return "text-bad";
    default:
      return "text-slate-300";
  }
}

export function statusBadge(status: string): string {
  const tone = decisionTone(status);
  return `inline-flex items-center rounded-full border border-edge px-2 py-0.5 text-xs font-medium ${tone}`;
}

export function eventLabel(type: string): string {
  const map: Record<string, string> = {
    shipment_accepted: "Shipment accepted (clean)",
    run_created: "Recovery loop ran",
    run_approved: "Escalation approved",
    run_rejected: "Escalation rejected",
    run_corrected: "Human correction applied",
    metrics: "Metrics updated",
    law_veto: "Law veto applied",
    lesson_promoted: "Lesson promoted",
    drift_alert: "Drift detected",
    demo_beat: "Demo beat",
    demo_complete: "Demo complete",
    reset: "Board reset",
  };
  return map[type] ?? type;
}
