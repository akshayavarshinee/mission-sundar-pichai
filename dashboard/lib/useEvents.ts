"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "./api";

// The backend SSE stream names each event (event: <type>) and sends the full
// envelope {type, ts, data} as JSON in the data field.
export interface ClearEvent {
  type: string;
  ts: string;
  data: Record<string, unknown>;
}

const EVENT_TYPES = [
  "shipment_accepted",
  "run_created",
  "run_approved",
  "run_rejected",
  "metrics",
  "law_veto",
  "lesson_promoted",
  "drift_alert",
  "demo_beat",
  "demo_complete",
  "reset",
];

// Subscribe to the live event bus with automatic reconnect. Returns the rolling
// log (newest first) and a connection flag so the UI can show a status dot.
export function useEvents(limit = 200): {
  events: ClearEvent[];
  connected: boolean;
} {
  const [events, setEvents] = useState<ClearEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    const push = (raw: string) => {
      try {
        const evt = JSON.parse(raw) as ClearEvent;
        setEvents((prev) => [evt, ...prev].slice(0, limit));
      } catch {
        /* ignore malformed frame */
      }
    };

    const connect = () => {
      if (closed) return;
      const es = new EventSource(`${API_BASE}/api/events`);
      sourceRef.current = es;

      es.onopen = () => setConnected(true);
      EVENT_TYPES.forEach((t) =>
        es.addEventListener(t, (e) => push((e as MessageEvent).data))
      );
      es.onmessage = (e) => push(e.data); // fallback for unnamed frames

      es.onerror = () => {
        setConnected(false);
        es.close();
        if (!closed) retry = setTimeout(connect, 1500); // reconnect
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      sourceRef.current?.close();
    };
  }, [limit]);

  return { events, connected };
}
