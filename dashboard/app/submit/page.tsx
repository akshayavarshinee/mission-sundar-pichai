"use client";

import SubmitForm from "@/components/submit/SubmitForm";

export default function SubmitPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">New shipment</h1>
        <p className="text-sm text-muted">
          File a cross-border customs declaration and let ClearPort clear it — or recover it if it’s
          rejected.
        </p>
      </div>
      <SubmitForm />
    </div>
  );
}
