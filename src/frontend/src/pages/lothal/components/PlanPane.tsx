// The Workspace's right pane during the PLAN stage (Epic U-PLAN). Unlike the
// PROTOTYPE pane (which embeds Open Design's own UI in an iframe), this is a
// NATIVE surface: the verification-driven PM tree is *our* product, so the pane
// renders it directly from the canonical Lothal API
// (`/api/v1/lothal/projects/{id}/plan/*`), which the backend bridges to the
// standalone PM service. The browser never talks to that service directly.
//
// Master-detail: the node hierarchy on the left, a selected node's validation
// panel on the right — its assume-guarantee contract, verification criteria, and
// the roll-up RATIFY gate (whose failure reason flows through from the PM service).
// Editing + ratify are live only while the project is in PLAN; afterwards the tree
// is read-only. Add nodes below; Approve advances to code generation.

import { useEffect, useState } from "react";
import type { Project } from "@/controllers/API/queries/lothal";
import {
  type PlanNode,
  type PlanNodeKind,
  type TestMethodology,
  type TestScope,
  useApprovePlan,
  useCreatePlanNode,
  useCreatePlanTest,
  usePlan,
  usePlanNode,
  usePlanTests,
  useRatifyPlanNode,
  useTransitionPlanNode,
  useUpdatePlanContract,
  useUpdatePlanCriteria,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";
import { isNotImplemented, NotReady } from "./NotReady";

const KINDS: PlanNodeKind[] = ["app", "component", "epic", "story"];
const METHODOLOGIES: TestMethodology[] = ["unit", "integration", "system", "acceptance"];

const STATE_COLOR: Record<string, string> = {
  draft: "var(--ink-soft)",
  ratified: "#2f8f83",
  in_progress: "#3e7ab8",
  in_verification: "#6f5bd0",
  verified: "var(--success)",
  failed: "#c0552e",
  invalidated: "#c0552e",
};

// The PM service's user-facing reason (the ratify-gate verdict) rides on a 4xx.
function reasonOf(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail;
  if (typeof detail === "string") return detail;
  return error ? "Something went wrong." : null;
}

const toLines = (s: string): string[] =>
  s.split("\n").map((x) => x.trim()).filter(Boolean);

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
        whiteSpace: "nowrap",
      }}
    >
      {state.replace(/_/g, " ")}
    </span>
  );
}

const fieldLabel = {
  fontSize: 9.5,
  letterSpacing: "0.06em",
  textTransform: "uppercase" as const,
  color: "var(--ink-mute)",
};
const areaStyle = {
  width: "100%",
  fontSize: 12.5,
  lineHeight: 1.5,
  padding: "7px 10px",
  border: "1px solid var(--border)",
  borderRadius: 8,
  background: "var(--paper)",
  color: "var(--ink)",
  resize: "vertical" as const,
};

function ListField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={fieldLabel}>{label}</span>
      <textarea
        rows={3}
        value={value}
        disabled={disabled}
        placeholder="one per line"
        onChange={(e) => onChange(e.target.value)}
        style={{ ...areaStyle, opacity: disabled ? 0.7 : 1 }}
      />
    </label>
  );
}

const TEST_SCOPES: TestScope[] = ["unit", "integration"];

function NodeTests({
  projectId,
  nodeId,
  canEdit,
}: {
  projectId: string;
  nodeId: string;
  canEdit: boolean;
}) {
  const { data: tests } = usePlanTests(projectId, nodeId);
  const createTest = useCreatePlanTest(projectId, nodeId);
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState<TestScope>("unit");

  const add = () => {
    const t = title.trim();
    if (!t || createTest.isPending) return;
    createTest.mutate({ scope, title: t }, { onSuccess: () => setTitle("") });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-soft)" }}>
        Tests
      </span>
      {(tests ?? []).length === 0 ? (
        <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>No tests yet.</span>
      ) : (
        (tests ?? []).map((t) => (
          <div
            key={t.id}
            style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}
          >
            <span style={{ fontSize: 9.5, color: "var(--ink-mute)", width: 64 }}>
              {t.scope}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>{t.title}</span>
            {t.latest_status && <StateChip state={t.latest_status} />}
          </div>
        ))
      )}
      {canEdit && (
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") add();
            }}
            placeholder="New test title…"
            style={{ ...areaStyle, flex: 1, resize: undefined }}
          />
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as TestScope)}
            style={{ ...areaStyle, resize: undefined, maxWidth: 130 }}
          >
            {TEST_SCOPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="sm"
            disabled={!title.trim() || createTest.isPending}
            onClick={add}
          >
            Add test
          </Button>
        </div>
      )}
    </div>
  );
}

function NodeDetailPanel({
  projectId,
  nodeId,
  editable,
}: {
  projectId: string;
  nodeId: string;
  editable: boolean;
}) {
  const { data: node, isLoading, error } = usePlanNode(projectId, nodeId);
  const saveContract = useUpdatePlanContract(projectId, nodeId);
  const saveCriteria = useUpdatePlanCriteria(projectId, nodeId);
  const ratify = useRatifyPlanNode(projectId);
  const reopen = useTransitionPlanNode(projectId);

  const [assumptions, setAssumptions] = useState("");
  const [guarantees, setGuarantees] = useState("");
  const [criteria, setCriteria] = useState("");
  const [acceptance, setAcceptance] = useState("");
  const [methodology, setMethodology] = useState<TestMethodology>("unit");

  // Re-seed the editors whenever the node (or its revision) changes.
  useEffect(() => {
    if (!node) return;
    setAssumptions((node.contract?.assumptions ?? []).join("\n"));
    setGuarantees((node.contract?.guarantees ?? []).join("\n"));
    setCriteria((node.verification_criteria ?? []).join("\n"));
    setAcceptance((node.acceptance_criteria ?? []).join("\n"));
    setMethodology((node.test_methodology as TestMethodology) ?? "unit");
    ratify.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.id, node?.updated_at]);

  if (isLoading) return <PaneLoading label="Loading node…" />;
  if (error || !node)
    return <NotReady title="Couldn't load the node" error={error ?? undefined} />;

  const isDraft = node.state === "draft";
  const canEdit = editable && isDraft;
  const ratifyReason = ratify.isError ? reasonOf(ratify.error) : null;

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: "14px 16px",
        overflowY: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 9.5, color: "var(--ink-mute)" }}>{node.kind}</span>
        <span style={{ flex: 1, minWidth: 0, fontSize: 15, fontWeight: 600 }}>
          {node.name}
        </span>
        <StateChip state={node.state} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-soft)" }}>
          Assume–guarantee contract
        </span>
        <ListField
          label="Assumptions"
          value={assumptions}
          onChange={setAssumptions}
          disabled={!canEdit}
        />
        <ListField
          label="Guarantees"
          value={guarantees}
          onChange={setGuarantees}
          disabled={!canEdit}
        />
        {canEdit && (
          <div>
            <Button
              variant="secondary"
              size="sm"
              disabled={saveContract.isPending}
              onClick={() =>
                saveContract.mutate({
                  assumptions: toLines(assumptions),
                  guarantees: toLines(guarantees),
                })
              }
            >
              {saveContract.isPending ? "Saving…" : "Save contract"}
            </Button>
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-soft)" }}>
          Verification criteria
        </span>
        <ListField
          label="Definition of done"
          value={criteria}
          onChange={setCriteria}
          disabled={!canEdit}
        />
        <ListField
          label="Acceptance criteria"
          value={acceptance}
          onChange={setAcceptance}
          disabled={!canEdit}
        />
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={fieldLabel}>Test methodology</span>
          <select
            value={methodology}
            disabled={!canEdit}
            onChange={(e) => setMethodology(e.target.value as TestMethodology)}
            style={{
              ...areaStyle,
              opacity: canEdit ? 1 : 0.7,
              resize: undefined,
              maxWidth: 200,
            }}
          >
            {METHODOLOGIES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        {canEdit && (
          <div>
            <Button
              variant="secondary"
              size="sm"
              disabled={saveCriteria.isPending}
              onClick={() =>
                saveCriteria.mutate({
                  verification_criteria: toLines(criteria),
                  acceptance_criteria: toLines(acceptance),
                  test_methodology: methodology,
                })
              }
            >
              {saveCriteria.isPending ? "Saving…" : "Save criteria"}
            </Button>
          </div>
        )}
      </div>

      <NodeTests projectId={projectId} nodeId={node.id} canEdit={canEdit} />

      {/* The ratify gate. Its failure reason is the PM service's own verdict. */}
      {editable && (
        <div
          style={{
            marginTop: "auto",
            paddingTop: 12,
            borderTop: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {isDraft ? (
            <Button
              variant="accent"
              disabled={ratify.isPending}
              onClick={() => ratify.mutate(node.id)}
            >
              {ratify.isPending ? "Ratifying…" : "Ratify node"}
            </Button>
          ) : (
            <Button
              variant="outline"
              disabled={reopen.isPending}
              onClick={() => reopen.mutate({ nodeId: node.id, target: "draft" })}
            >
              {reopen.isPending ? "Reopening…" : "Reopen to edit"}
            </Button>
          )}
          {ratifyReason && (
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.5,
                color: "#c0552e",
                background: "color-mix(in srgb, #c0552e 8%, transparent)",
                border: "1px solid color-mix(in srgb, #c0552e 30%, transparent)",
                borderRadius: 8,
                padding: "8px 10px",
              }}
            >
              <strong>Gate not satisfied — </strong>
              {ratifyReason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NodeRow({
  node,
  selected,
  onSelect,
}: {
  node: PlanNode;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = STATE_COLOR[node.state] ?? "var(--ink-mute)";
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        textAlign: "left",
        padding: "7px 10px",
        paddingLeft: 10 + node.depth * 18,
        border: "none",
        borderBottom: "1px solid var(--border)",
        borderLeft: selected
          ? "2px solid var(--accent)"
          : "2px solid transparent",
        background: selected ? "var(--surface)" : "transparent",
        cursor: "pointer",
        color: "var(--ink)",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
        }}
      />
      <span style={{ flex: 1, minWidth: 0, fontSize: 13 }}>{node.name}</span>
      <span style={{ fontSize: 9.5, color: "var(--ink-mute)" }}>{node.kind}</span>
    </button>
  );
}

export function PlanPane({ project }: { project: Project }) {
  const { data, isLoading, error } = usePlan(project.id);
  const createNode = useCreatePlanNode(project.id);
  const approve = useApprovePlan(project.id);

  const [name, setName] = useState("");
  const [kind, setKind] = useState<PlanNodeKind>("component");
  const [parentId, setParentId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

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
  const editable = project.phase === "PLAN";

  const addNode = () => {
    const trimmed = name.trim();
    if (!trimmed || createNode.isPending) return;
    createNode.mutate(
      { kind, name: trimmed, parent_id: parentId || null },
      { onSuccess: (node) => {
          setName("");
          setSelected(node.id);
        } },
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
            {nodes.length} node{nodes.length === 1 ? "" : "s"} · {links.length} link
            {links.length === 1 ? "" : "s"}
            {!editable && " · read-only"}
          </span>
        </div>
        {editable && (
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
        )}
      </header>

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        {/* Tree (master) */}
        <div
          style={{
            width: 320,
            flexShrink: 0,
            borderRight: "1px solid var(--border)",
            overflowY: "auto",
          }}
        >
          {nodes.length === 0 ? (
            <div style={{ paddingTop: 48 }}>
              <EmptyHint
                title="An empty tree"
                sub="Add the top-level node to start planning the build."
              />
            </div>
          ) : (
            nodes.map((node) => (
              <NodeRow
                key={node.id}
                node={node}
                selected={selected === node.id}
                onSelect={() => setSelected(node.id)}
              />
            ))
          )}
        </div>

        {/* Detail */}
        <div style={{ flex: 1, minWidth: 0, background: "var(--paper-deep)" }}>
          {selected ? (
            <NodeDetailPanel
              key={selected}
              projectId={project.id}
              nodeId={selected}
              editable={editable}
            />
          ) : (
            <div style={{ paddingTop: 80 }}>
              <EmptyHint
                title="Select a node"
                sub="Pick a node to see its contract, criteria, and the ratify gate."
              />
            </div>
          )}
        </div>
      </div>

      {editable && (
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
      )}
    </div>
  );
}
