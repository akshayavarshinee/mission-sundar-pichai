"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import type { Declaration, SubmitPayload } from "@/lib/api";

// Lets a human correct the declaration before it clears — the hero
// human-in-the-loop step that feeds experiment-gated learning.
export default function CorrectionForm({
  declaration,
  busy,
  onSubmit,
  onCancel,
}: {
  declaration: Declaration;
  busy: boolean;
  onSubmit: (payload: SubmitPayload, note: string) => void;
  onCancel: () => void;
}) {
  const [hs, setHs] = useState<string[]>(
    declaration.items.map((i) => i.hs_tariff_number ?? "")
  );
  const [signer, setSigner] = useState(declaration.customs_signer ?? "");
  const [explanation, setExplanation] = useState(declaration.contents_explanation ?? "");
  const [restriction, setRestriction] = useState(declaration.restriction_comments ?? "");
  const [eel, setEel] = useState(declaration.eel_pfc ?? "");
  const [note, setNote] = useState("");

  const submit = () => {
    const payload: SubmitPayload = {
      contents_type: declaration.contents_type,
      customs_certify: declaration.customs_certify,
      customs_signer: signer.trim() || null,
      contents_explanation: explanation.trim() || null,
      restriction_type: declaration.restriction_type,
      restriction_comments: restriction.trim() || null,
      eel_pfc: eel.trim() || null,
      items: declaration.items.map((it, i) => ({
        description: it.description,
        quantity: it.quantity,
        value: it.value,
        weight_oz: it.weight_oz,
        origin_country: it.origin_country,
        hs_tariff_number: hs[i].trim() || null,
        currency: it.currency,
      })),
    };
    onSubmit(payload, note.trim());
  };

  const field = "w-full rounded-lg border border-edge bg-panel px-2.5 py-1.5 text-sm text-ink outline-none focus:border-accent/60";
  const label = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-faint";

  return (
    <div className="space-y-3 rounded-lg border border-edge bg-panel2 p-3">
      <div className="space-y-2">
        {declaration.items.map((it, i) => (
          <div key={i}>
            <label className={label}>HS code — {it.description}</label>
            <input
              className={`${field} font-mono`}
              value={hs[i]}
              onChange={(e) =>
                setHs((prev) => prev.map((v, j) => (j === i ? e.target.value : v)))
              }
              placeholder="e.g. 830249"
            />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <label className={label}>Customs signer</label>
          <input className={field} value={signer} onChange={(e) => setSigner(e.target.value)} />
        </div>
        <div>
          <label className={label}>EEI / EEL PFC</label>
          <input className={field} value={eel} onChange={(e) => setEel(e.target.value)} />
        </div>
        <div>
          <label className={label}>Contents explanation</label>
          <input
            className={field}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
          />
        </div>
        <div>
          <label className={label}>Restriction comments</label>
          <input
            className={field}
            value={restriction}
            onChange={(e) => setRestriction(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className={label}>Note (optional)</label>
        <input className={field} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>

      <div className="flex gap-2">
        <button className="btn btn-good flex-1" disabled={busy} onClick={submit}>
          <Check className="h-4 w-4" />
          {busy ? "Submitting…" : "Submit correction & buy label"}
        </button>
        <button className="btn" disabled={busy} onClick={onCancel}>
          <X className="h-4 w-4" />
          Cancel
        </button>
      </div>
    </div>
  );
}
