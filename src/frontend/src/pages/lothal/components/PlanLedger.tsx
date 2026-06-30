// PLAN stage — the decision/provenance ledger view. The PM tree records every
// state change, contract edit, ratification, link, and invalidation as an append-
// only event; this lists them newest-first. Read-only by nature.

import { type PlanEvent, usePlanActivity } from "@/controllers/API/queries/lothal";
import { EmptyHint } from "./EmptyHint";

// Tolerate the PM service's exact field names — build a human line from whatever
// the event carries (a summary, a state transition, or the bare event kind).
function eventLine(e: PlanEvent): string {
  if (e.summary) return e.summary;
  const kind = e.event_type ?? e.kind ?? "event";
  if (e.from_state || e.to_state) {
    return `${kind}: ${e.from_state ?? "—"} → ${e.to_state ?? "—"}`;
  }
  return e.detail ? `${kind} — ${e.detail}` : kind;
}

function stamp(iso: string): string {
  // Browser-local; tolerate an unparseable value rather than throw.
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function PlanLedger({ projectId }: { projectId: string }) {
  const { data: events, isLoading, error } = usePlanActivity(projectId);

  if (isLoading) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          color: "var(--ink-soft)",
        }}
      >
        Loading the ledger…
      </div>
    );
  }
  if (error || !events || events.length === 0) {
    return (
      <div style={{ paddingTop: 80 }}>
        <EmptyHint
          title="No activity yet"
          sub="Every decision — ratify, edit, link, invalidate — lands here as you build the plan."
        />
      </div>
    );
  }

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      {events.map((e) => (
        <div
          key={e.id}
          style={{
            display: "flex",
            gap: 12,
            padding: "9px 16px",
            borderBottom: "1px solid var(--border)",
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          <span
            style={{
              color: "var(--ink-mute)",
              fontSize: 11,
              whiteSpace: "nowrap",
              minWidth: 150,
            }}
          >
            {stamp(e.created_at)}
          </span>
          <span style={{ flex: 1, minWidth: 0 }}>{eventLine(e)}</span>
        </div>
      ))}
    </div>
  );
}
