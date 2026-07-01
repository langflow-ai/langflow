// PLAN stage — the dependency-graph view. An interactive, client-rendered DAG:
// selectable node cards laid out in depth columns, with typed, colour-coded peer
// edges and a legend. Clicking a node selects it (and returns to the tree detail).
// Below the canvas: the typed link list and, while editable, an add-link form.
//
// The layout is derived from the tree depth we already hold (column = depth, row
// = order within the column) — no server render round-trip, so the graph reacts
// to selection and edits immediately.

import { useMemo, useState } from "react";
import {
  type PlanLink,
  type PlanLinkType,
  type PlanNode,
  useCreatePlanLink,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";
import { Icon, KindTile } from "./plan/atoms";
import {
  KIND_COLOR,
  LINK_TYPES,
  linkMeta,
  stateColor,
  tint,
} from "./plan/planTheme";

const selectStyle = {
  fontSize: 12,
  padding: "6px 8px",
  border: "1px solid var(--border)",
  borderRadius: 8,
  background: "var(--paper)",
  color: "var(--ink)",
  minWidth: 0,
};

const CARD_W = 188;
const CARD_H = 62;
const COL_GAP = 230;
const ROW_GAP = 92;
const PAD = 24;

type Placed = PlanNode & { x: number; y: number };

function layout(nodes: PlanNode[]): {
  placed: Placed[];
  width: number;
  height: number;
} {
  const byDepth = new Map<number, PlanNode[]>();
  for (const n of nodes) {
    const d = Math.max(0, n.depth ?? 0);
    const col = byDepth.get(d) ?? [];
    col.push(n);
    byDepth.set(d, col);
  }
  const placed: Placed[] = [];
  let maxRows = 0;
  let maxDepth = 0;
  for (const [d, col] of Array.from(byDepth.entries())) {
    maxDepth = Math.max(maxDepth, d);
    maxRows = Math.max(maxRows, col.length);
    col.forEach((n, row) => {
      placed.push({
        ...n,
        x: PAD + d * COL_GAP,
        y: PAD + row * ROW_GAP,
      });
    });
  }
  return {
    placed,
    width: PAD * 2 + maxDepth * COL_GAP + CARD_W,
    height: PAD * 2 + Math.max(0, maxRows - 1) * ROW_GAP + CARD_H,
  };
}

function GraphCanvas({
  nodes,
  links,
  selectedId,
  onSelect,
}: {
  nodes: PlanNode[];
  links: PlanLink[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { placed, width, height } = useMemo(() => layout(nodes), [nodes]);
  const posOf = useMemo(() => {
    const m = new Map<string, Placed>();
    for (const p of placed) m.set(p.id, p);
    return m;
  }, [placed]);

  // Lock indicator: a parent in verification whose children aren't all verified.
  const lockedIds = useMemo(() => {
    const childStates = new Map<string, string[]>();
    for (const n of nodes) {
      if (n.parent_id)
        childStates.set(n.parent_id, [
          ...(childStates.get(n.parent_id) ?? []),
          n.state,
        ]);
    }
    const locked = new Set<string>();
    for (const n of nodes) {
      const cs = childStates.get(n.id);
      if (
        n.state === "in_verification" &&
        cs &&
        cs.some((s) => s !== "verified")
      )
        locked.add(n.id);
    }
    return locked;
  }, [nodes]);

  // Distinct marker per link colour (arrowheads inherit the edge hue).
  const markerColors = useMemo(
    () => Array.from(new Set(links.map((l) => linkMeta(l.link_type).color))),
    [links],
  );
  const markerId = (color: string) =>
    `plan-arr-${color.replace(/[^a-z0-9]/gi, "")}`;

  return (
    <div
      style={{
        position: "relative",
        width,
        height,
        margin: "auto",
        minWidth: "100%",
      }}
    >
      <svg
        width={width}
        height={height}
        style={{
          position: "absolute",
          inset: 0,
          overflow: "visible",
          pointerEvents: "none",
        }}
        aria-hidden
      >
        <defs>
          {markerColors.map((color) => (
            <marker
              key={color}
              id={markerId(color)}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L10 5 L0 10 z" fill={color} />
            </marker>
          ))}
        </defs>
        {links.map((l) => {
          const s = posOf.get(l.source_id);
          const t = posOf.get(l.target_id);
          // Skip dangling links (a peer missing from nodes[]) and self-links,
          // both of which would render as degenerate geometry.
          if (!s || !t || l.source_id === l.target_id) return null;
          const sy = s.y + CARD_H / 2;
          const ty = t.y + CARD_H / 2;
          const meta = linkMeta(l.link_type);
          const touchesSel =
            selectedId != null &&
            (l.source_id === selectedId || l.target_id === selectedId);
          // Anchor on whichever sides keep the curve OUTSIDE the cards: a forward
          // edge exits the source's right and enters the target's left; a backward
          // edge mirrors it; a same-column edge bows out to the right of both so it
          // never cuts through the stacked cards.
          let sx: number;
          let tx: number;
          let cx1: number;
          let cx2: number;
          if (Math.abs(t.x - s.x) < 1) {
            sx = s.x + CARD_W;
            tx = t.x + CARD_W;
            cx1 = sx + 48;
            cx2 = tx + 48;
          } else {
            const forward = t.x > s.x;
            sx = forward ? s.x + CARD_W : s.x;
            tx = forward ? t.x : t.x + CARD_W;
            const dx = Math.max(40, Math.abs(tx - sx) / 2);
            cx1 = forward ? sx + dx : sx - dx;
            cx2 = forward ? tx - dx : tx + dx;
          }
          const d = `M ${sx} ${sy} C ${cx1} ${sy}, ${cx2} ${ty}, ${tx} ${ty}`;
          return (
            <path
              key={l.id}
              d={d}
              fill="none"
              stroke={meta.color}
              strokeWidth={touchesSel ? 2.4 : 1.6}
              strokeDasharray={meta.dash === "none" ? undefined : meta.dash}
              markerEnd={`url(#${markerId(meta.color)})`}
              opacity={selectedId == null || touchesSel ? 1 : 0.3}
            />
          );
        })}
      </svg>

      {placed.map((n) => {
        const selected = n.id === selectedId;
        const hue = KIND_COLOR[n.kind];
        return (
          <button
            key={n.id}
            type="button"
            onClick={() => onSelect(n.id)}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              width: CARD_W,
              height: CARD_H,
              display: "flex",
              alignItems: "center",
              gap: 9,
              padding: "0 12px",
              borderRadius: 11,
              border: `1.5px solid ${selected ? hue : "var(--border)"}`,
              background: "var(--surface)",
              boxShadow: selected ? `0 0 0 4px ${tint(hue, 18)}` : "none",
              cursor: "pointer",
              textAlign: "left",
              color: "var(--ink)",
            }}
          >
            <KindTile kind={n.kind} size={26} />
            <span
              style={{
                flex: 1,
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
                gap: 3,
              }}
            >
              <span
                style={{
                  fontSize: 12.5,
                  fontWeight: 500,
                  color: "var(--ink)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {n.name}
              </span>
              <span
                style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: stateColor(n.state),
                    flex: "none",
                  }}
                />
                <span style={{ fontSize: 10.5, color: "var(--ink-soft)" }}>
                  {n.state.replace(/_/g, " ")}
                </span>
              </span>
            </span>
            {lockedIds.has(n.id) && (
              <span
                title="Roll-up gate locked"
                style={{
                  color: "var(--ink-soft)",
                  display: "inline-flex",
                  flex: "none",
                }}
              >
                <Icon.Lock size={11} />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function PlanGraph({
  projectId,
  nodes,
  links,
  editable,
  selectedId,
  onSelect,
}: {
  projectId: string;
  nodes: PlanNode[];
  links: PlanLink[];
  editable: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const createLink = useCreatePlanLink(projectId);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [type, setType] = useState<PlanLinkType>("derives_from");

  const nameOf = (id: string) =>
    nodes.find((n) => n.id === id)?.name ?? id.slice(0, 8);

  const addLink = () => {
    if (!source || !target || source === target || createLink.isPending) return;
    createLink.mutate(
      { source_id: source, target_id: target, link_type: type },
      {
        onSuccess: () => {
          setSource("");
          setTarget("");
        },
      },
    );
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Legend */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "10px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--paper)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
          typed peer links · the DAG
        </span>
        <span style={{ flex: 1 }} />
        {LINK_TYPES.map((lt) => {
          const meta = linkMeta(lt);
          return (
            <span
              key={lt}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11.5,
                color: "var(--ink-mute)",
              }}
            >
              <span
                style={{
                  width: 18,
                  height: 0,
                  borderTop: `2px ${meta.dash === "none" ? "solid" : "dashed"} ${meta.color}`,
                }}
              />
              <span className="mono" style={{ fontSize: 11 }}>
                {lt}
              </span>
              {meta.invalidation && (
                <span style={{ color: "#cf9a3a", display: "inline-flex" }}>
                  <Icon.Warn size={11} />
                </span>
              )}
            </span>
          );
        })}
      </div>

      {/* Canvas */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "auto",
          padding: 12,
          background:
            "radial-gradient(color-mix(in srgb, var(--ink) 8%, transparent) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
          display: "flex",
        }}
      >
        {nodes.length === 0 ? (
          <div style={{ margin: "auto" }}>
            <EmptyHint
              title="No graph yet"
              sub="Add nodes and dependency links to see the DAG."
            />
          </div>
        ) : (
          <GraphCanvas
            nodes={nodes}
            links={links}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
      </div>

      {/* Link list + add form */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "10px 14px",
          maxHeight: 230,
          overflowY: "auto",
          background: "var(--surface)",
        }}
      >
        <span
          style={{
            fontSize: 9.5,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "var(--ink-mute)",
          }}
        >
          Dependency links · {links.length}
        </span>
        <div style={{ marginTop: 6 }}>
          {links.length === 0 ? (
            <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>
              No links yet.
            </span>
          ) : (
            links.map((l) => {
              const meta = linkMeta(l.link_type);
              return (
                <div
                  key={l.id}
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    padding: "4px 0",
                    fontSize: 12.5,
                  }}
                >
                  <span>{nameOf(l.source_id)}</span>
                  <span
                    className="mono"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      padding: "1px 7px",
                      borderRadius: 5,
                      background: tint(meta.color, 15),
                      color: meta.color,
                    }}
                  >
                    {l.link_type}
                  </span>
                  <span>{nameOf(l.target_id)}</span>
                </div>
              );
            })
          )}
        </div>

        {editable && nodes.length >= 2 && (
          <div
            style={{
              display: "flex",
              gap: 6,
              marginTop: 10,
              alignItems: "center",
            }}
          >
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">source…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as PlanLinkType)}
              style={selectStyle}
            >
              {LINK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">target…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              size="sm"
              disabled={
                !source || !target || source === target || createLink.isPending
              }
              onClick={addLink}
            >
              Link
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
