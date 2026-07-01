// The per-node Dependencies & links card — surfaces the typed peer links that
// touch this node (incoming + outgoing) right where you work, instead of only in
// the separate graph view. Each row deep-links to its peer; `derives_from` is
// flagged as the invalidation channel.

import type { PlanLink, PlanNode } from "@/controllers/API/queries/lothal";
import { Icon, StateChip } from "./atoms";
import { linkMeta, stateColor, tint } from "./planTheme";

type Row = {
  key: string;
  dir: "OUT" | "INC";
  type: string;
  invalidation: boolean;
  peer: PlanNode | null;
  peerId: string;
};

const Card = ({ children }: { children: React.ReactNode }) => (
  <div
    style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 14,
      padding: "16px 18px",
    }}
  >
    {children}
  </div>
);

export function NodeLinksCard({
  nodeId,
  nodes,
  links,
  onSelect,
  onOpenGraph,
}: {
  nodeId: string;
  nodes: PlanNode[];
  links: PlanLink[];
  onSelect: (id: string) => void;
  onOpenGraph: () => void;
}) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const rows: Row[] = links
    .filter((l) => l.source_id === nodeId || l.target_id === nodeId)
    .map((l) => {
      const out = l.source_id === nodeId;
      const peerId = out ? l.target_id : l.source_id;
      return {
        key: l.id,
        dir: out ? "OUT" : "INC",
        type: l.link_type,
        invalidation: linkMeta(l.link_type).invalidation,
        peer: byId.get(peerId) ?? null,
        peerId,
      };
    });

  const hasDerives = rows.some((r) => r.invalidation);

  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 13,
        }}
      >
        <div className="label" style={{ color: "var(--ink-mute)" }}>
          Dependencies &amp; links
        </div>
        <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>
          the DAG · traceability
        </span>
        <button
          type="button"
          onClick={onOpenGraph}
          style={{
            marginLeft: "auto",
            fontFamily: "var(--sans)",
            fontSize: 11,
            fontWeight: 500,
            color: "var(--ink)",
            background: "transparent",
            border: "1px solid var(--border-strong)",
            borderRadius: 7,
            padding: "4px 10px",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <Icon.Graph size={12} />
          Open graph
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.length === 0 ? (
          <div
            style={{
              fontSize: 12,
              color: "var(--ink-soft)",
              padding: "4px 2px",
            }}
          >
            No typed links on this node.
          </div>
        ) : (
          rows.map((r) => {
            const meta = linkMeta(r.type);
            return (
              <button
                key={r.key}
                type="button"
                disabled={!r.peer}
                title={
                  r.peer
                    ? undefined
                    : "Peer node is unavailable in this snapshot"
                }
                onClick={() => {
                  if (r.peer) onSelect(r.peerId);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 11px",
                  cursor: r.peer ? "pointer" : "default",
                  opacity: r.peer ? 1 : 0.6,
                  border: "1px solid var(--border)",
                  borderRadius: 9,
                  background: "var(--paper)",
                  textAlign: "left",
                  width: "100%",
                  color: "var(--ink)",
                }}
              >
                <span
                  className="label"
                  style={{ fontSize: 9, width: 26, flex: "none" }}
                >
                  {r.dir}
                </span>
                <span
                  className="mono"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "2px 7px",
                    borderRadius: 5,
                    background: tint(meta.color, 15),
                    color: meta.color,
                    flex: "none",
                  }}
                >
                  {r.type}
                </span>
                {r.invalidation && (
                  <span
                    title="invalidation channel"
                    style={{
                      color: "#cf9a3a",
                      display: "inline-flex",
                      flex: "none",
                    }}
                  >
                    <Icon.Warn size={12} />
                  </span>
                )}
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 2,
                    background: r.peer
                      ? stateColor(r.peer.state)
                      : "var(--ink-faint)",
                    flex: "none",
                  }}
                />
                <span
                  style={{
                    flex: 1,
                    fontSize: 12.5,
                    color: "var(--ink)",
                    fontWeight: 500,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {r.peer?.name ?? r.peerId.slice(0, 8)}
                </span>
                {r.peer && <StateChip state={r.peer.state} />}
              </button>
            );
          })
        )}
      </div>

      {hasDerives && (
        <div
          style={{
            marginTop: 11,
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            fontSize: 11.5,
            color: "var(--ink-mute)",
            background: tint("#cf9a3a", 8),
            border: `1px solid ${tint("#cf9a3a", 30)}`,
            borderRadius: 9,
            padding: "9px 11px",
          }}
        >
          <span
            style={{
              color: "#cf9a3a",
              display: "inline-flex",
              flex: "none",
              marginTop: 1,
            }}
          >
            <Icon.Warn size={13} />
          </span>
          <span>
            <b style={{ color: "var(--ink)", fontWeight: 600 }}>derives_from</b>{" "}
            is the invalidation channel — if a target re-ratifies with changed
            guarantees, this node auto-invalidates.
          </span>
        </div>
      )}
    </Card>
  );
}
