import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { statusMeta, toneSoft, type StatusGroup } from "@/lib/shipment";

const GROUP_ICON: Record<StatusGroup, React.ComponentType<{ className?: string }>> = {
  cleared: CheckCircle2,
  attention: Clock,
  rejected: XCircle,
};

// A single, consistent status chip used everywhere a shipment status appears.
export default function StatusPill({
  status,
  size = "md",
}: {
  status: string;
  size?: "sm" | "md";
}) {
  const meta = statusMeta(status);
  const Icon = GROUP_ICON[meta.group];
  const pad = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${pad} ${toneSoft[meta.tone]}`}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {meta.label}
    </span>
  );
}
