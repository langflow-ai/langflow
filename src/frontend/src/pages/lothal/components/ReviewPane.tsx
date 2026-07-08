// ReviewPane (prod_spec.md Part B) — a read-only, four-panel review of the code a
// node produced. Native panes, no iframe. Driven by a two-level selection:
//   • OUTER — the node tree (right) selects a *node* → sets the commit range and
//     repopulates every panel.
//   • INNER — the file manager (top-left) selects a *file* → swaps only the middle
//     panel.
//
// Layout (spec target):
//   ┌───────────────┬─────────────────────────┬──────────────┐
//   │ File manager  │                         │              │
//   │ (tree @after, │   File / Diff view      │  Node tree   │
//   │  changed tags)│   (whole-node diff by   │  (DAG, the   │
//   ├───────────────┤    default; per-file    │   master     │
//   │ Ledger        │    Monaco on click)     │   selector)  │
//   │ (audit/       │                         │              │
//   │  decisions)   │                         │              │
//   └───────────────┴─────────────────────────┴──────────────┘
//
// This file is the shell + shared selection state. The panels are filled in by the
// later stages (node tree → Stage 3, whole-node diff → Stage 4, file manager →
// Stage 5, per-file view → Stage 6, ledger → Stage 7). Until then each renders an
// explicit empty state, so the shell is demoable on its own.

import { type CSSProperties, type ReactNode, useMemo, useState } from "react";
import {
  type FileTreeNode,
  type LedgerEvent,
  type PlanNode,
  type Project,
  useNodeDiff,
  useNodeFileTree,
  useNodeLedger,
  useReviewTree,
} from "@/controllers/API/queries/lothal";
import { EmptyHint } from "./EmptyHint";
import { isNotImplemented, NotReady } from "./NotReady";
import { ReviewDiff } from "./ReviewDiff";
import { ReviewFileView } from "./ReviewFileView";

// The single outer selection: a node and its derived commit range. `null` until the
// user picks a node in the tree.
export type ReviewSelection = {
  nodeId: string;
  nodeName: string;
};

function PanelFrame({
  title,
  right,
  children,
  style,
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        minWidth: 0,
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          padding: "7px 12px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
          flex: "none",
        }}
      >
        <span
          className="label"
          style={{
            fontSize: 10.5,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "var(--ink-soft)",
          }}
        >
          {title}
        </span>
        {right}
      </div>
      <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflow: "auto" }}>
        {children}
      </div>
    </div>
  );
}

// --- Panels (stubs until their stage lands) ----------------------------------

// Node lifecycle → a status dot (mirrors the PM `NodeState` enum). The tree shows a
// node's state inline so a reviewer sees passed / failed / in-progress at a glance.
const NODE_STATE: Record<string, { color: string; label: string }> = {
  draft: { color: "var(--ink-faint)", label: "draft" },
  ratified: { color: "#3e7ab8", label: "ratified" },
  in_progress: { color: "#c08a2e", label: "in progress" },
  in_verification: { color: "#6f5bd0", label: "verifying" },
  verified: { color: "var(--success)", label: "verified" },
  failed: { color: "var(--warn)", label: "failed" },
  invalidated: { color: "var(--ink-soft)", label: "invalidated" },
};

type ForestNode = PlanNode & { children: ForestNode[] };

// Rebuild the tree from the flat node list (each carries parent_id + depth). Order is
// preserved from the server; missing parents fall back to roots so nothing is lost.
function buildForest(nodes: PlanNode[]): ForestNode[] {
  const byId = new Map<string, ForestNode>();
  for (const n of nodes) byId.set(n.id, { ...n, children: [] });
  const roots: ForestNode[] = [];
  for (const n of nodes) {
    const self = byId.get(n.id)!;
    const parent = n.parent_id ? byId.get(n.parent_id) : undefined;
    if (parent) parent.children.push(self);
    else roots.push(self);
  }
  return roots;
}

function StateDot({ state }: { state: string }) {
  const s = NODE_STATE[state] ?? { color: "var(--ink-faint)", label: state };
  return (
    <span
      title={s.label}
      aria-label={s.label}
      style={{
        flex: "none",
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: s.color,
      }}
    />
  );
}

function NodeRow({
  node,
  selectedId,
  onSelect,
}: {
  node: ForestNode;
  selectedId: string | null;
  onSelect: (s: ReviewSelection) => void;
}) {
  const active = node.id === selectedId;
  return (
    <>
      <button
        type="button"
        onClick={() => onSelect({ nodeId: node.id, nodeName: node.name })}
        title={`${node.name} · ${NODE_STATE[node.state]?.label ?? node.state}`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "6px 10px",
          paddingLeft: 10 + node.depth * 14,
          border: "none",
          borderLeft: active
            ? "2px solid var(--accent)"
            : "2px solid transparent",
          background: active ? "var(--surface)" : "transparent",
          color: "inherit",
          cursor: "pointer",
          textAlign: "left",
          font: "inherit",
        }}
      >
        <StateDot state={node.state} />
        <span
          style={{
            fontSize: 12.5,
            color: active ? "var(--ink)" : "var(--ink-mute)",
            fontWeight: active ? 600 : 400,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {node.name}
        </span>
      </button>
      {node.children.map((c) => (
        <NodeRow
          key={c.id}
          node={c}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

const CENTERED: CSSProperties = {
  height: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 13,
  color: "var(--ink-soft)",
  padding: 16,
};

function NodeTreePanel({
  project,
  selection,
  onSelect,
}: {
  project: Project;
  selection: ReviewSelection | null;
  onSelect: (s: ReviewSelection | null) => void;
}) {
  const { data, isLoading, isError, error } = useReviewTree(project.id);
  const forest = useMemo(() => (data ? buildForest(data.nodes) : []), [data]);

  if (isLoading) return <div style={CENTERED}>Loading the tree…</div>;
  if (isError) {
    return isNotImplemented(error) ? (
      <NotReady title="Review isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the tree"
        detail="Something went wrong loading the verification tree. Try again in a moment."
      />
    );
  }
  if (!data || data.nodes.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <EmptyHint
          title="No nodes yet"
          sub="Nodes appear here as the plan is built and its code is generated."
        />
      </div>
    );
  }

  return (
    <div style={{ padding: "6px 0" }}>
      {forest.map((n) => (
        <NodeRow
          key={n.id}
          node={n}
          selectedId={selection?.nodeId ?? null}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

// The header shown above a per-file view — the path + a way back to the whole-node
// diff. Switching files never refetches node-level data (the diff is cached), and
// closing restores the whole-node diff.
function FileViewHeader({
  path,
  onClose,
}: {
  path: string;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 12px",
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
        flex: "none",
      }}
    >
      <button
        type="button"
        onClick={onClose}
        title="Back to the whole-node diff"
        style={{
          fontSize: 11,
          color: "var(--ink-mute)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          background: "transparent",
          padding: "2px 8px",
          cursor: "pointer",
          flex: "none",
        }}
      >
        ← All changes
      </button>
      <span
        className="mono"
        style={{
          fontSize: 11.5,
          color: "var(--ink)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {path}
      </span>
    </div>
  );
}

function DiffPanel({
  project,
  selection,
  selectedFile,
  onClearFile,
}: {
  project: Project;
  selection: ReviewSelection | null;
  selectedFile: string | null;
  onClearFile: () => void;
}) {
  const { data, isLoading, isError, error } = useNodeDiff(
    project.id,
    selection?.nodeId ?? null,
  );

  if (!selection) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
        }}
      >
        <EmptyHint
          title="Select a node to review"
          sub="Its whole-node diff shows here; click a file to open it on its own."
        />
      </div>
    );
  }
  if (isLoading) return <div style={CENTERED}>Loading the diff…</div>;
  if (isError) {
    return isNotImplemented(error) ? (
      <NotReady title="Review isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the diff"
        detail="Something went wrong computing this node's diff. Try again in a moment."
      />
    );
  }
  if (!data) return <div style={CENTERED}>No diff.</div>;

  // INNER selection: a file is open → the per-file Monaco view (Stage 6). Otherwise the
  // whole-node diff (Stage 4). Both read the same cached node diff.
  if (selectedFile) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <FileViewHeader path={selectedFile} onClose={onClearFile} />
        <div style={{ flex: 1, minHeight: 0 }}>
          <ReviewFileView
            projectId={project.id}
            nodeId={selection.nodeId}
            path={selectedFile}
            diff={data}
          />
        </div>
      </div>
    );
  }
  return <ReviewDiff diff={data} />;
}

// change-status → a compact one-letter tag in the file tree (git-status style). The
// status comes from the SAME node diff the middle panel renders, so annotations can
// never drift from the diff.
const FILE_STATUS: Record<string, { label: string; color: string }> = {
  added: { label: "A", color: "var(--success)" },
  modified: { label: "M", color: "#c08a2e" },
  deleted: { label: "D", color: "var(--warn)" },
  renamed: { label: "R", color: "#6f5bd0" },
  copied: { label: "C", color: "#3e7ab8" },
  "type-changed": { label: "T", color: "var(--ink-soft)" },
};

function FileTreeRow({
  node,
  depth,
  statusOf,
  selectedFile,
  onFileSelect,
}: {
  node: FileTreeNode;
  depth: number;
  statusOf: (path: string) => string | undefined;
  selectedFile: string | null;
  onFileSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const pad = 8 + depth * 12;

  if (node.type === "tree") {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            width: "100%",
            padding: "3px 8px",
            paddingLeft: pad,
            border: "none",
            background: "transparent",
            color: "var(--ink-soft)",
            cursor: "pointer",
            textAlign: "left",
            font: "inherit",
          }}
        >
          <span style={{ fontSize: 9, width: 8, flex: "none" }}>
            {open ? "▾" : "▸"}
          </span>
          <span style={{ fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {node.name}
          </span>
        </button>
        {open &&
          node.children.map((c) => (
            <FileTreeRow
              key={c.path}
              node={c}
              depth={depth + 1}
              statusOf={statusOf}
              selectedFile={selectedFile}
              onFileSelect={onFileSelect}
            />
          ))}
      </>
    );
  }

  const status = statusOf(node.path);
  const meta = status ? FILE_STATUS[status] : undefined;
  const active = node.path === selectedFile;
  return (
    <button
      type="button"
      onClick={() => onFileSelect(node.path)}
      title={node.path}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        width: "100%",
        padding: "3px 8px",
        paddingLeft: pad + 13,
        border: "none",
        borderLeft: active
          ? "2px solid var(--accent)"
          : "2px solid transparent",
        background: active ? "var(--surface)" : "transparent",
        color: "inherit",
        cursor: "pointer",
        textAlign: "left",
        font: "inherit",
      }}
    >
      <span
        style={{
          fontSize: 12,
          color: active ? "var(--ink)" : status ? "var(--ink-mute)" : "var(--ink-soft)",
          fontWeight: active ? 600 : 400,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          flex: 1,
        }}
      >
        {node.name}
      </span>
      {meta && (
        <span
          title={status}
          className="mono"
          style={{ fontSize: 10, fontWeight: 700, color: meta.color, flex: "none" }}
        >
          {meta.label}
        </span>
      )}
    </button>
  );
}

function FileManagerPanel({
  project,
  selection,
  selectedFile,
  onFileSelect,
}: {
  project: Project;
  selection: ReviewSelection | null;
  selectedFile: string | null;
  onFileSelect: (path: string) => void;
}) {
  const nodeId = selection?.nodeId ?? null;
  const tree = useNodeFileTree(project.id, nodeId);
  // The diff drives the change-status annotations (same source as the middle panel).
  const diff = useNodeDiff(project.id, nodeId);
  const statusOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const f of diff.data?.files ?? []) m.set(f.path, f.status);
    return (path: string) => m.get(path);
  }, [diff.data]);

  if (!selection) {
    return (
      <div style={{ padding: 14 }}>
        <EmptyHint title="Files" sub="Select a node to list its files." />
      </div>
    );
  }
  if (tree.isLoading) return <div style={CENTERED}>Loading files…</div>;
  if (tree.isError) {
    return isNotImplemented(tree.error) ? (
      <NotReady title="Review isn't live yet" error={tree.error} />
    ) : (
      <NotReady
        title="Couldn't load the files"
        detail="Something went wrong loading this node's file tree."
      />
    );
  }
  if (!tree.data || tree.data.root.length === 0) {
    return (
      <div style={{ padding: 14 }}>
        <EmptyHint
          title="No files"
          sub="This node has no committed files yet."
        />
      </div>
    );
  }

  return (
    <div style={{ padding: "6px 0" }}>
      {tree.data.root.map((n) => (
        <FileTreeRow
          key={n.path}
          node={n}
          depth={0}
          statusOf={statusOf}
          selectedFile={selectedFile}
          onFileSelect={onFileSelect}
        />
      ))}
    </div>
  );
}

// Who acted — the ledger's headline distinction (human decision vs the agent/LLM).
const ACTOR: Record<string, { label: string; color: string }> = {
  human: { label: "You", color: "var(--accent)" },
  agent: { label: "Agent", color: "#c08a2e" },
  system: { label: "System", color: "var(--ink-soft)" },
};

function humanizeEvent(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function LedgerEventRow({ event }: { event: LedgerEvent }) {
  const actor = ACTOR[event.actor_type] ?? {
    label: event.actor_type,
    color: "var(--ink-soft)",
  };
  return (
    <div
      style={{
        display: "flex",
        gap: 9,
        padding: "8px 12px",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span
        title={`${actor.label} · ${event.actor_type}`}
        style={{
          flex: "none",
          marginTop: 3,
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: actor.color,
        }}
      />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 6,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{ fontSize: 11.5, fontWeight: 600, color: actor.color }}
          >
            {actor.label}
          </span>
          <span
            className="mono"
            style={{ fontSize: 10.5, color: "var(--ink-soft)" }}
          >
            {humanizeEvent(event.event_type)}
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-mute)", marginTop: 2 }}>
          {event.summary}
        </div>
      </div>
    </div>
  );
}

function LedgerPanel({
  project,
  selection,
}: {
  project: Project;
  selection: ReviewSelection | null;
}) {
  const nodeId = selection?.nodeId ?? null;
  const { data, isLoading, isError, error } = useNodeLedger(project.id, nodeId);

  if (!selection) {
    return (
      <div style={{ padding: 14 }}>
        <EmptyHint title="Ledger" sub="Select a node to see its audit trail." />
      </div>
    );
  }
  if (isLoading) return <div style={CENTERED}>Loading the ledger…</div>;
  if (isError) {
    return isNotImplemented(error) ? (
      <NotReady title="Review isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the ledger"
        detail="Something went wrong loading this node's audit trail."
      />
    );
  }
  if (!data || data.events.length === 0) {
    return (
      <div style={{ padding: 14 }}>
        <EmptyHint
          title="No audit entries yet"
          sub="Decisions, tests, and the agent's steps appear here as the node is built."
        />
      </div>
    );
  }

  const passed = data.tests.filter((t) => t.status === "passed").length;
  const failed = data.tests.filter((t) => t.status === "failed").length;

  return (
    <div>
      {(data.tests.length > 0 || data.codegen) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "7px 12px",
            borderBottom: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: 11.5,
            color: "var(--ink-soft)",
          }}
        >
          {data.tests.length > 0 && (
            <span>
              Tests:{" "}
              <b style={{ color: "var(--success)" }}>{passed} passed</b>
              {failed > 0 && (
                <>
                  {" · "}
                  <b style={{ color: "var(--warn)" }}>{failed} failed</b>
                </>
              )}
            </span>
          )}
          {data.codegen && typeof data.codegen.state === "string" && (
            <span>Codegen: {String(data.codegen.state)}</span>
          )}
        </div>
      )}
      {data.events.map((e) => (
        <LedgerEventRow key={e.id} event={e} />
      ))}
    </div>
  );
}

export function ReviewPane({ project }: { project: Project }) {
  // OUTER selection (the node) and INNER selection (a file within it), kept strictly
  // separate: a file click swaps only the middle panel; a node change resets the file.
  const [selection, setSelection] = useState<ReviewSelection | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const selectNode = (s: ReviewSelection | null) => {
    setSelection(s);
    setSelectedFile(null); // switching node restores the whole-node diff
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(220px, 300px) minmax(0, 1fr) minmax(200px, 280px)",
        height: "100%",
        minHeight: 0,
        background: "var(--paper)",
      }}
    >
      {/* Left column — file manager (top) over ledger (bottom). */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          borderRight: "1px solid var(--border)",
        }}
      >
        <PanelFrame title="Files" style={{ flex: 1, minHeight: 0 }}>
          <FileManagerPanel
            project={project}
            selection={selection}
            selectedFile={selectedFile}
            onFileSelect={setSelectedFile}
          />
        </PanelFrame>
        <PanelFrame
          title="Ledger"
          style={{ flex: 1, minHeight: 0, borderTop: "1px solid var(--border)" }}
        >
          <LedgerPanel project={project} selection={selection} />
        </PanelFrame>
      </div>

      {/* Centre — the diff / per-file view. */}
      <div style={{ minWidth: 0, background: "var(--paper-deep)" }}>
        <PanelFrame
          title={selection ? `Diff · ${selection.nodeName}` : "Diff"}
          style={{ height: "100%" }}
        >
          <DiffPanel
            project={project}
            selection={selection}
            selectedFile={selectedFile}
            onClearFile={() => setSelectedFile(null)}
          />
        </PanelFrame>
      </div>

      {/* Right — the node tree master selector. */}
      <div style={{ borderLeft: "1px solid var(--border)", minHeight: 0 }}>
        <PanelFrame title="Nodes" style={{ height: "100%" }}>
          <NodeTreePanel
            project={project}
            selection={selection}
            onSelect={selectNode}
          />
        </PanelFrame>
      </div>
    </div>
  );
}
