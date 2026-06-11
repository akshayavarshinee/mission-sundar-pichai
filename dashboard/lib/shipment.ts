// Product-level semantics: turn a raw recovery "run" into a "shipment case"
// with human-friendly status, plain-English explanations, and display helpers.
import type { RunSummary } from "./api";

export type Tone = "good" | "warn" | "bad" | "veto" | "accent" | "muted";

export type StatusGroup = "cleared" | "attention" | "rejected";

export interface StatusMeta {
  group: StatusGroup;
  label: string;
  short: string;
  tone: Tone;
}

const STATUS: Record<string, StatusMeta> = {
  AUTO_RESOLVED: { group: "cleared", label: "Auto-cleared", short: "Cleared", tone: "good" },
  HUMAN_APPROVED: { group: "cleared", label: "Approved & cleared", short: "Cleared", tone: "good" },
  HUMAN_CORRECTED: { group: "cleared", label: "Corrected & cleared", short: "Cleared", tone: "good" },
  AWAITING_APPROVAL: { group: "attention", label: "Needs your approval", short: "Needs you", tone: "warn" },
  HUMAN_REJECTED: { group: "rejected", label: "Rejected by you", short: "Rejected", tone: "bad" },
  REJECTED: { group: "rejected", label: "Could not clear", short: "Failed", tone: "bad" },
};

export function statusMeta(status: string): StatusMeta {
  return (
    STATUS[status] ?? { group: "attention", label: status, short: status, tone: "muted" }
  );
}

// Tone → tailwind class fragments (colours come from the CSS-var theme).
export const toneText: Record<Tone, string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
  veto: "text-veto",
  accent: "text-accent",
  muted: "text-muted",
};

export const toneDot: Record<Tone, string> = {
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
  veto: "bg-veto",
  accent: "bg-accent",
  muted: "bg-faint",
};

export const toneSoft: Record<Tone, string> = {
  good: "border-good/30 bg-good/10 text-good",
  warn: "border-warn/30 bg-warn/10 text-warn",
  bad: "border-bad/30 bg-bad/10 text-bad",
  veto: "border-veto/30 bg-veto/10 text-veto",
  accent: "border-accent/30 bg-accent/10 text-accent",
  muted: "border-edge bg-panel2 text-muted",
};

// Human-readable name for each normalized customs error.
const ERROR_LABELS: Record<string, string> = {
  HS_INVALID: "Invalid HS tariff code",
  EEI_THRESHOLD_MISMATCH: "EEI filing required",
  RESTRICTION_COMMENTS_MISSING: "Missing restriction details",
  SIGNER_MISSING: "Missing customs signer",
  CONTENTS_EXPLANATION_MISSING: "Missing contents explanation",
  ZERO_VALUE: "Invalid line value",
  OVERLAY_SCHEMA_DRIFT: "Destination rule changed",
  UNKNOWN: "Unrecognized rejection",
};

// One-sentence, plain-English explanation an operator can understand.
const ERROR_BLURBS: Record<string, string> = {
  HS_INVALID:
    "The declared tariff code isn’t a valid 6- or 10-digit HTS number, so customs can’t classify the goods.",
  EEI_THRESHOLD_MISMATCH:
    "The shipment is at or above the $2,500 EEI threshold but was filed as exempt (NOEEI).",
  RESTRICTION_COMMENTS_MISSING:
    "The goods are flagged restricted but no restriction comments were provided.",
  SIGNER_MISSING:
    "The declaration is certified but no customs signer was named.",
  CONTENTS_EXPLANATION_MISSING:
    "Contents are marked “other” but no explanation of what they are was given.",
  ZERO_VALUE:
    "A line item has a non-positive value, quantity, or weight.",
  OVERLAY_SCHEMA_DRIFT:
    "The destination quietly changed a validation rule, so a previously-passing filing now fails.",
  UNKNOWN: "The carrier returned a rejection ClearPort could not map to a known cause.",
};

export function errorLabel(errorType: string): string {
  return ERROR_LABELS[errorType] ?? errorType;
}

export function errorBlurb(errorType: string): string {
  return ERROR_BLURBS[errorType] ?? "";
}

export function prettyLane(origin: string, dest: string): string {
  return `${origin} → ${dest}`;
}

const CONTENTS_LABELS: Record<string, string> = {
  merchandise: "Merchandise",
  gift: "Gift",
  documents: "Documents",
  sample: "Sample",
  return_merchandise: "Return",
  other: "Other",
};

export function contentsLabel(contents: string): string {
  return CONTENTS_LABELS[contents] ?? contents;
}

export function decisionLabel(decision: string): string {
  switch (decision.toUpperCase()) {
    case "AUTO":
      return "Auto-resolve";
    case "HUMAN":
      return "Route to human";
    default:
      return decision;
  }
}

// Whether this case is still waiting on the operator.
export function needsAttention(run: RunSummary): boolean {
  return run.status === "AWAITING_APPROVAL";
}
