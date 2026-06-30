// The Workspace's right pane during the PLAN stage (Epic U-PLAN). Unlike the
// PROTOTYPE pane (which embeds Open Design's own UI in an iframe), this is a
// NATIVE surface: the verification-driven PM tree is *our* product, so the pane
// renders it directly from the canonical Lothal API
// (`/api/v1/lothal/projects/{id}/plan/*`), which the backend bridges to the
// standalone PM service. The browser never talks to that service directly.
//
// The pane shows the node hierarchy (name + kind + state, indented by depth) and
// its dependency links, lets the user add nodes, and Approves the plan to advance
// to code generation.
//
// States:
//   not PLAN phase  → nothing (the Workspace only mounts this in PLAN)
//   loading         → "opening" line
//   501 (stub)      → NotReady ("not live yet")
//   other error     → NotReady ("couldn't load")
//   ready           → the tree + add-node form + Approve

import { useState } from "react";
import type { Project } from "@/controllers/API/queries/lothal";
import {
  type PlanNode,
  type PlanNodeKind,
  useApprovePlan,
  useCreatePlanNode,
  usePlan,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";
import { isNotImplemented, NotReady } from "./NotReady";

const KINDS: PlanNodeKind[] = ["app", "component", "epic", "story"];

// A node's verification state, shown as a small colored chip. The PM service's
// states walk draft → ratified/verified → invalidated; we colour the common ones
// and fall back to neutral for anything else.
const STATE_COLOR: Record<string, string> = {
  draft: "var(--ink-soft)",
  ratified: "#2f8f83",
  verified: "var(--success)",
  invalidated: "#c0552e",
};

function PaneLoading({ label }: { label: string }) {
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
      {label}
    </div>
  );
}

function StateChip({ state }: { state: string }) {
  const color = STATE_COLOR[state] ?? "var(--ink-mute)";
  return (
    <span
      style={{
        fontSize: 10,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        color,
        border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
        borderRadius: 5,
        padding: "1px 6px",
      }}
    >
      {state}
    </span>
  );
}

function NodeRow({ node }: { node: PlanNode }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 10px",
        marginLeft: node.depth * 18,
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span
        className="label"
        style={{ fontSize: 9.5, color: "var(--ink-mute)", width: 64 }}
      >
        {node.kind}
      </span>
      <span style={{ flex: 1, minWidth: 0, fontSize: 13 }}>{node.name}</span>
      <StateChip state={node.state} />
    </div>
  );
}

export function PlanPane({ project }: { project: Project }) {
  const { data, isLoading, error } = usePlan(project.id);
  const createNode = useCreatePlanNode(project.id);
  const approve = useApprovePlan(project.id);

  const [name, setName] = useState("");
  const [kind, setKind] = useState<PlanNodeKind>("component");
  const [parentId, setParentId] = useState("");

  if (isLoading) return <PaneLoading label="Opening the plan…" />;
  if (error) {
    return isNotImplemented(error) ? (
      <NotReady title="Planning isn't live yet" error={error} />
    ) : (
      <NotReady title="Couldn't load the plan" error={error} />
    );
  }
  if (!data) return <PaneLoading label="Opening the plan…" />;

  const { nodes, links } = data;

  const addNode = () => {
    const trimmed = name.trim();
    if (!trimmed || createNode.isPending) return;
    createNode.mutate(
      { kind, name: trimmed, parent_id: parentId || null },
      { onSuccess: () => setName("") },
    );
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "12px 16px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Planning tree</span>
          <span style={{ fontSize: 11.5, color: "var(--ink-mute)" }}>
            {nodes.length} node{nodes.length === 1 ? "" : "s"} · {links.length}{" "}
            link{links.length === 1 ? "" : "s"}
          </span>
        </div>
        <Button
          onClick={() => approve.mutate()}
          disabled={approve.isPending || nodes.length === 0}
          title={
            nodes.length === 0
              ? "Add at least one node before approving"
              : "Approve the plan and move to code generation"
          }
        >
          {approve.isPending ? "Approving…" : "Approve plan"}
        </Button>
      </header>

      <div style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
        {nodes.length === 0 ? (
          <div style={{ paddingTop: 56 }}>
            <EmptyHint
              title="An empty tree"
              sub="Add the top-level node to start planning the build."
            />
          </div>
        ) : (
          nodes.map((node) => <NodeRow key={node.id} node={node} />)
        )}
      </div>

      <footer
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 12px",
          borderTop: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addNode();
          }}
          placeholder="New node name…"
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 13,
            padding: "7px 10px",
            border: "1px solid var(--border)",
            borderRadius: 8,
            background: "var(--paper)",
            color: "var(--ink)",
          }}
        />
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as PlanNodeKind)}
          style={{
            fontSize: 12,
            padding: "7px 8px",
            border: "1px solid var(--border)",
            borderRadius: 8,
            background: "var(--paper)",
            color: "var(--ink)",
          }}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <select
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          title="Parent node (optional)"
          style={{
            fontSize: 12,
            padding: "7px 8px",
            border: "1px solid var(--border)",
            borderRadius: 8,
            background: "var(--paper)",
            color: "var(--ink)",
            maxWidth: 140,
          }}
        >
          <option value="">— root —</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
        <Button onClick={addNode} disabled={!name.trim() || createNode.isPending}>
          Add
        </Button>
      </footer>
    </div>
  );
}
