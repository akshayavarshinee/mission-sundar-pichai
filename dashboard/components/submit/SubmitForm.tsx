"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Send, Sparkles } from "lucide-react";
import type { SubmitRequest } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";

interface FormState {
  description: string;
  quantity: number;
  value: number;
  weight: number;
  hs: string;
  origin: string;
  dest: string;
  contentsType: string;
  signer: string;
  shipper: string;
  restrictionType: string;
  restrictionComments: string;
  eel: string;
  explanation: string;
  certify: boolean;
}

const BLANK: FormState = {
  description: "",
  quantity: 1,
  value: 100,
  weight: 16,
  hs: "",
  origin: "IN",
  dest: "US",
  contentsType: "merchandise",
  signer: "",
  shipper: "",
  restrictionType: "none",
  restrictionComments: "",
  eel: "NOEEI 30.37(a)",
  explanation: "",
  certify: true,
};

// Quick-fill scenarios so an operator can see each recovery path without typing.
const PRESETS: { label: string; hint: string; patch: Partial<FormState> }[] = [
  {
    label: "Invalid HS code",
    hint: "auto-classified",
    patch: { description: "Hand-engraved brass keychain", quantity: 10, value: 80, weight: 16, hs: "1234", signer: "Anaya Sharma", contentsType: "merchandise", restrictionType: "none" },
  },
  {
    label: "Missing signer",
    hint: "fast auto-heal",
    patch: { description: "Hand-block-printed silk scarf", quantity: 1, value: 90, weight: 6, hs: "621440", signer: "", contentsType: "merchandise", restrictionType: "none" },
  },
  {
    label: "Over $2,500 (EEI)",
    hint: "escalates to you",
    patch: { description: "Cotton knit t-shirts (lot)", quantity: 80, value: 3200, weight: 320, hs: "610910", signer: "Anaya Sharma", eel: "NOEEI 30.37(a)", contentsType: "merchandise", restrictionType: "none" },
  },
  {
    label: "Restricted goods",
    hint: "danger escalate",
    patch: { description: "Assorted spice sampler", quantity: 1, value: 40, weight: 12, hs: "090411", signer: "Anaya Sharma", restrictionType: "quarantine", restrictionComments: "", contentsType: "merchandise" },
  },
  {
    label: "Clean shipment",
    hint: "no recovery",
    patch: { description: "Hand-block-printed silk scarf", quantity: 1, value: 90, weight: 6, hs: "621440", signer: "Anaya Sharma", contentsType: "merchandise", restrictionType: "none" },
  },
];

export default function SubmitForm() {
  const router = useRouter();
  const { submit, busy } = useWorkspace();
  const [f, setF] = useState<FormState>(BLANK);
  const [accepted, setAccepted] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setF((prev) => ({ ...prev, [k]: v }));

  const applyPreset = (patch: Partial<FormState>) => {
    setAccepted(false);
    setErr(null);
    setF({ ...BLANK, ...patch });
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setAccepted(false);
    const body: SubmitRequest = {
      origin: f.origin.trim().toUpperCase(),
      dest: f.dest.trim().toUpperCase(),
      persona: f.shipper.trim() ? `${f.shipper.trim()} (${f.origin}→${f.dest})` : null,
      shipper_name: f.shipper.trim() || null,
      payload: {
        contents_type: f.contentsType,
        customs_certify: f.certify,
        customs_signer: f.signer.trim() || null,
        contents_explanation: f.explanation.trim() || null,
        restriction_type: f.restrictionType,
        restriction_comments: f.restrictionComments.trim() || null,
        eel_pfc: f.eel.trim() || null,
        items: [
          {
            description: f.description.trim() || "Unnamed goods",
            quantity: Number(f.quantity),
            value: Number(f.value),
            weight_oz: Number(f.weight),
            origin_country: f.origin.trim().toUpperCase(),
            hs_tariff_number: f.hs.trim() || null,
            currency: "USD",
          },
        ],
      },
    };
    try {
      const res = await submit(body);
      if ("run_id" in res) {
        router.push(`/shipments/${res.run_id}`);
      } else {
        setAccepted(true);
      }
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const field =
    "w-full rounded-lg border border-edge bg-panel px-3 py-2 text-sm text-ink outline-none focus:border-accent/60";
  const label = "mb-1 block text-xs font-medium text-muted";

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form onSubmit={onSubmit} className="card space-y-4 p-5 lg:col-span-2">
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-faint">
            Start from an example
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => applyPreset(p.patch)}
                className="group rounded-lg border border-edge bg-panel2 px-2.5 py-1.5 text-left text-xs transition hover:border-accent/60"
              >
                <span className="font-medium text-body">{p.label}</span>
                <span className="ml-1.5 text-faint">{p.hint}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-edge pt-4">
          <label className={label}>Goods description</label>
          <input
            className={field}
            value={f.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="e.g. Hand-block-printed silk scarf"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className={label}>Quantity</label>
            <input type="number" min={1} className={field} value={f.quantity} onChange={(e) => set("quantity", Number(e.target.value))} />
          </div>
          <div>
            <label className={label}>Value (USD)</label>
            <input type="number" min={0} className={field} value={f.value} onChange={(e) => set("value", Number(e.target.value))} />
          </div>
          <div>
            <label className={label}>Weight (oz)</label>
            <input type="number" min={0} className={field} value={f.weight} onChange={(e) => set("weight", Number(e.target.value))} />
          </div>
          <div>
            <label className={label}>HS code</label>
            <input className={`${field} font-mono`} value={f.hs} onChange={(e) => set("hs", e.target.value)} placeholder="6 or 10 digits" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className={label}>Origin</label>
            <input className={`${field} uppercase`} value={f.origin} maxLength={2} onChange={(e) => set("origin", e.target.value)} />
          </div>
          <div>
            <label className={label}>Destination</label>
            <input className={`${field} uppercase`} value={f.dest} maxLength={2} onChange={(e) => set("dest", e.target.value)} />
          </div>
          <div className="col-span-2">
            <label className={label}>Contents type</label>
            <select className={field} value={f.contentsType} onChange={(e) => set("contentsType", e.target.value)}>
              {["merchandise", "gift", "sample", "documents", "return_merchandise", "other"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className={label}>Shipper / business name</label>
            <input className={field} value={f.shipper} onChange={(e) => set("shipper", e.target.value)} placeholder="optional" />
          </div>
          <div>
            <label className={label}>Customs signer</label>
            <input className={field} value={f.signer} onChange={(e) => set("signer", e.target.value)} placeholder="leave blank to test signer recovery" />
          </div>
          <div>
            <label className={label}>EEI / EEL PFC</label>
            <input className={field} value={f.eel} onChange={(e) => set("eel", e.target.value)} />
          </div>
          <div>
            <label className={label}>Restriction type</label>
            <select className={field} value={f.restrictionType} onChange={(e) => set("restrictionType", e.target.value)}>
              {["none", "other", "quarantine", "sanitary_phytosanitary_inspection"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          {f.restrictionType !== "none" ? (
            <div className="sm:col-span-2">
              <label className={label}>Restriction comments</label>
              <input className={field} value={f.restrictionComments} onChange={(e) => set("restrictionComments", e.target.value)} placeholder="leave blank to test restriction recovery" />
            </div>
          ) : null}
          {f.contentsType === "other" ? (
            <div className="sm:col-span-2">
              <label className={label}>Contents explanation</label>
              <input className={field} value={f.explanation} onChange={(e) => set("explanation", e.target.value)} placeholder="leave blank to test explanation recovery" />
            </div>
          ) : null}
        </div>

        <label className="flex items-center gap-2 text-sm text-body">
          <input type="checkbox" checked={f.certify} onChange={(e) => set("certify", e.target.checked)} className="h-4 w-4 rounded border-edge" />
          Certify this declaration
        </label>

        {err ? <p className="text-sm text-bad">{err}</p> : null}
        {accepted ? (
          <div className="flex items-center gap-2 rounded-lg border border-good/30 bg-good/5 p-3 text-sm text-good">
            <CheckCircle2 className="h-4 w-4" />
            Declaration is clean — it passed customs with nothing to recover.
          </div>
        ) : null}

        <button type="submit" className="btn btn-accent w-full" disabled={busy === "submit"}>
          <Send className="h-4 w-4" />
          {busy === "submit" ? "Submitting…" : "Submit declaration"}
        </button>
      </form>

      <aside className="space-y-3">
        <div className="card p-5">
          <h2 className="section-title mb-2">
            <Sparkles className="h-4 w-4 text-accent" />
            What happens next
          </h2>
          <ol className="space-y-2.5 text-sm text-muted">
            {[
              "We validate your declaration on the real carrier surface (EasyPost test mode).",
              "If it’s rejected, the Auditor diagnoses the cause against customs law + memory.",
              "The Patch Engine rewrites the declaration to fix it.",
              "The Arize eval-gate must approve the fix before any money is spent.",
              "Low-risk fixes auto-clear; high-value or restricted ones come to you.",
            ].map((s, i) => (
              <li key={i} className="flex gap-2.5">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-[11px] font-semibold text-accent">
                  {i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
        </div>
        <p className="px-1 text-xs text-faint">
          Tip: leave the customs signer blank, use a 4-digit HS code, or set a value above $2,500 to
          watch ClearPort recover (or safely escalate) a real rejection.
        </p>
      </aside>
    </div>
  );
}
