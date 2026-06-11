import IntelligenceView from "@/components/intelligence/IntelligenceView";

// The Intelligence dashboard lives in a dedicated client view that renders the
// full self-learning + Arize Phoenix story (telemetry, learning curve,
// eval-gate, self-heal, memory tiers, promoted lessons, law, live traces).
export default function IntelligencePage() {
  return <IntelligenceView />;
}
