// The Workspace's right pane during the PLAN stage (Epic U-PLAN). Unlike the
// PROTOTYPE pane (which embeds Open Design's own UI in an iframe), this is a
// NATIVE surface: the verification-driven PM tree is *our* product, so the pane
// renders it directly from the canonical Lothal API
// (`/api/v1/lothal/projects/{id}/plan/*`), which the backend bridges to the
// standalone PM service. The browser never talks to that service directly.
//
// Master-detail: the verification tree on the left, a selected node's validation
// panel on the right — its assume-guarantee contract, verification criteria, the
// roll-up gate, typed links, the state machine, and (as a preview) the build-side
// Implementation view. Editing + transitions are live only while the project is
// in PLAN; afterwards the tree is read-only. Approve advances to code generation.

import { useEffect, useMemo, useState } from "react";
import type { PlanLink, Project } from "@/controllers/API/queries/lothal";
import {
  type PlanEvent,
  type PlanNode,
  type PlanNodeKind,
  type PlanTest,
  type TestMethodology,
  type TestScope,
  useApprovePlan,
  useCreatePlanNode,
  useCreatePlanTest,
  useMovePlanNode,
  usePlan,
  usePlanNode,
  usePlanNodeEvents,
  usePlanTests,
  useRatifyPlanNode,
  useRecordPlanTestRun,
  useTransitionPlanNode,
  useUpdatePlanContract,
  useUpdatePlanCriteria,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";
import { isNotImplemented, NotReady } from "./NotReady";
import { PlanGraph } from "./PlanGraph";
import { PlanLedger } from "./PlanLedger";
import {
  Icon,
  KindTile,
  MiniBar,
  StateChip,
  TestStatusChip,
} from "./plan/atoms";
import { GateHero, isGateOpen } from "./plan/GateHero";
import { ImplementationView } from "./plan/ImplementationView";
import { NodeLinksCard } from "./plan/NodeLinksCard";
import { NodeStateStepper } from "./plan/NodeStateStepper";
import {
  allowedTransitions,
  KIND_ABBR,
  KIND_COLOR,
  tint,
  verifiedRatio,
} from "./plan/planTheme";

type PlanView = "tree" | "graph" | "ledger";

// Node states that count as "frozen" — its definition of done is locked, so the
// plan can be approved. `draft` (never ratified) and `failed`/`invalidated`
// (needs rework) do not, and block plan approval.
const RATIFIED_OR_BEYOND = new Set([
  "ratified",
  "in_progress",
  "in_verification",
  "verified",
]);

function ViewTabs({
  view,
  onChange,
}: {
  view: PlanView;
  onChange: (v: PlanView) => void;
}) {
  const tabs: { id: PlanView; label: string }[] = [
    { id: "tree", label: "Tree" },
    { id: "graph", label: "Graph" },
    { id: "ledger", label: "Ledger" },
  ];
  return (
    <div
      style={{
        display: "inline-flex",
        border: "1px solid var(--border)",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          style={{
            fontSize: 12,
            padding: "5px 14px",
            border: "none",
            cursor: "pointer",
            background: view === t.id ? "var(--ink)" : "transparent",
            color: view === t.id ? "var(--paper)" : "var(--ink-soft)",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

const KINDS: PlanNodeKind[] = ["app", "component", "epic", "story"];
const METHODOLOGIES: TestMethodology[] = [
  "unit",
  "integration",
  "system",
  "acceptance",
];

// The PM service's user-facing reason (the gate verdict) rides on a 4xx.
function reasonOf(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return error ? "Something went wrong." : null;
}

const toLines = (s: string): string[] =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

const eventStamp = (iso: string): string => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString();
};
const eventLabel = (e: PlanEvent): string =>
  e.summary ||
  (e.from_state || e.to_state
    ? `${e.from_state ?? "—"} → ${e.to_state ?? "—"}`
    : e.event_type || e.kind || "event");

const runBtn = (color: string) => ({
  fontSize: 10,
  padding: "2px 7px",
  borderRadius: 5,
  cursor: "pointer",
  border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
  background: "transparent",
  color,
});

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

// A titled card — the consistent container for every node-detail section.
function Card({
  label,
  aside,
  children,
}: {
  label?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: "16px 18px",
      }}
    >
      {label && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 14,
          }}
        >
          <div className="label" style={{ color: "var(--ink-mute)" }}>
            {label}
          </div>
          {aside}
        </div>
      )}
      {children}
    </div>
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

// A small frozen/editable chip used on the contract + criteria cards.
function FrozenChip({ frozen }: { frozen: boolean }) {
  const hue = frozen ? "var(--ink-soft)" : "var(--state-ratified)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        fontSize: 9.5,
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        color: hue,
        background: tint(hue, 14),
        border: `1px solid ${tint(hue, 30)}`,
        borderRadius: 5,
        padding: "1px 6px",
      }}
    >
      {frozen ? "Frozen" : "Editable"}
      {frozen && <Icon.Lock size={9} />}
    </span>
  );
}

// An icon-bulleted read list (assumptions use an arrow, guarantees a check).
function BulletList({
  items,
  variant,
}: {
  items: string[];
  variant: "assume" | "guarantee";
}) {
  if (items.length === 0)
    return (
      <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>
        None recorded.
      </div>
    );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 7,
            fontSize: 12.5,
            color: "var(--ink-90)",
          }}
        >
          <span
            style={{
              color:
                variant === "guarantee"
                  ? "var(--state-verified)"
                  : "var(--ink-soft)",
              marginTop: 2,
              flex: "none",
            }}
          >
            {variant === "guarantee" ? (
              <Icon.Check size={13} />
            ) : (
              <Icon.ArrowRight size={13} />
            )}
          </span>
          <span>{it}</span>
        </div>
      ))}
    </div>
  );
}

const TEST_SCOPES: TestScope[] = ["unit", "integration"];

function NodeTests({
  projectId,
  nodeId,
  tests,
  loading,
  error,
  canEdit,
  canRun,
}: {
  projectId: string;
  nodeId: string;
  tests: PlanTest[];
  loading: boolean;
  error: boolean;
  canEdit: boolean;
  canRun: boolean;
}) {
  const createTest = useCreatePlanTest(projectId, nodeId);
  const recordRun = useRecordPlanTestRun(projectId, nodeId);
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState<TestScope>("unit");

  const add = () => {
    const t = title.trim();
    if (!t || createTest.isPending) return;
    createTest.mutate({ scope, title: t }, { onSuccess: () => setTitle("") });
  };

  // Distinguish a failed/loading query from a genuinely empty test set — otherwise
  // a request failure reads as "no tests" and the gate can't be trusted.
  const emptyLabel = error
    ? "Couldn't load tests — the planning service may be unavailable."
    : loading
      ? "Loading tests…"
      : "No tests authored yet.";

  return (
    <Card label="Tests">
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {tests.length === 0 ? (
          <span
            style={{
              fontSize: 12,
              color: error ? "var(--state-failed)" : "var(--ink-mute)",
            }}
          >
            {emptyLabel}
          </span>
        ) : (
          tests.map((t) => (
            <div
              key={t.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                border: "1px solid var(--border)",
                borderRadius: 9,
                background: "var(--paper)",
                fontSize: 12.5,
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 9.5,
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                  fontWeight: 600,
                  padding: "2px 7px",
                  borderRadius: 5,
                  background: tint(
                    t.scope === "integration" ? "#c074b0" : "#5b8dc9",
                    15,
                  ),
                  color: t.scope === "integration" ? "#c074b0" : "#5b8dc9",
                  flex: "none",
                }}
              >
                {t.scope}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>{t.title}</span>
              {t.frozen && (
                <span
                  title="frozen"
                  style={{ color: "var(--ink-soft)", display: "inline-flex" }}
                >
                  <Icon.Lock size={10} />
                </span>
              )}
              {t.latest_status && <TestStatusChip status={t.latest_status} />}
              {canRun && (
                <span style={{ display: "inline-flex", gap: 4 }}>
                  <button
                    type="button"
                    title="Record a passing run"
                    disabled={recordRun.isPending}
                    onClick={() =>
                      recordRun.mutate({ testId: t.id, status: "passed" })
                    }
                    style={runBtn("var(--state-verified)")}
                  >
                    pass
                  </button>
                  <button
                    type="button"
                    title="Record a failing run"
                    disabled={recordRun.isPending}
                    onClick={() =>
                      recordRun.mutate({ testId: t.id, status: "failed" })
                    }
                    style={runBtn("var(--state-failed)")}
                  >
                    fail
                  </button>
                </span>
              )}
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
    </Card>
  );
}

// The full transition palette — one button per allowed edge out of the current
// state (reference ALLOWED map). draft→ratified routes through the ratify gate
// endpoint (which freezes the contract); every other edge uses the transition
// endpoint. Either can be refused by the PM service, whose reason we surface.
const TRANSITION_LABEL: Record<string, string> = {
  ratified: "Ratify & freeze",
  in_progress: "Start work",
  in_verification: "Send to verification",
  verified: "Mark verified",
  failed: "Mark failed",
  invalidated: "Invalidate",
  draft: "Reopen to draft",
};
const FORWARD = new Set([
  "ratified",
  "in_progress",
  "in_verification",
  "verified",
]);

function TransitionBar({
  state,
  gateOpen,
  onTransition,
  pending,
  reason,
}: {
  state: string;
  gateOpen: boolean;
  onTransition: (target: string) => void;
  pending: boolean;
  reason: string | null;
}) {
  const targets = allowedTransitions(state);

  return (
    <Card label="Transitions">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 9,
          alignItems: "center",
        }}
      >
        {targets.length === 0 ? (
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            Terminal state — no transitions available.
          </span>
        ) : (
          targets.map((target) => {
            // Pre-empt a verify that the reconstructed gate would block; the
            // server stays authoritative for everything else.
            const blocked = target === "verified" && !gateOpen;
            const forward = FORWARD.has(target);
            return (
              <Button
                key={target}
                variant={forward ? "accent" : "outline"}
                size="sm"
                disabled={pending || blocked}
                title={
                  blocked
                    ? "Roll-up gate locked — every check must be green first"
                    : undefined
                }
                onClick={() => onTransition(target)}
              >
                {TRANSITION_LABEL[target] ?? target.replace(/_/g, " ")}
              </Button>
            );
          })
        )}
      </div>
      {reason && (
        <div
          style={{
            marginTop: 11,
            display: "flex",
            alignItems: "flex-start",
            gap: 7,
            fontSize: 12,
            lineHeight: 1.5,
            color: "var(--ink-mute)",
            background: tint("#cf9a3a", 8),
            border: `1px solid ${tint("#cf9a3a", 30)}`,
            borderRadius: 9,
            padding: "8px 11px",
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
            <Icon.Warn size={14} />
          </span>
          <span>
            <strong style={{ color: "var(--ink)", fontWeight: 600 }}>
              Gate not satisfied —{" "}
            </strong>
            {reason}
          </span>
        </div>
      )}
    </Card>
  );
}

function ViewToggle({
  mode,
  onChange,
}: {
  mode: "item" | "impl";
  onChange: (m: "item" | "impl") => void;
}) {
  const btn = (m: "item" | "impl", label: string, icon: React.ReactNode) => {
    const active = mode === m;
    return (
      <button
        type="button"
        onClick={() => onChange(m)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontFamily: "var(--sans)",
          fontSize: 12.5,
          fontWeight: active ? 600 : 500,
          padding: "5px 12px",
          borderRadius: 7,
          border: "none",
          cursor: "pointer",
          background: active ? "var(--surface)" : "transparent",
          color: active ? "var(--ink)" : "var(--ink-soft)",
          boxShadow: active ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
        }}
      >
        {icon}
        {label}
      </button>
    );
  };
  return (
    <div
      style={{
        display: "inline-flex",
        gap: 3,
        padding: 3,
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: 9,
      }}
    >
      {btn("item", "Item", <Icon.Eye size={14} />)}
      {btn("impl", "Implementation", <Icon.Code size={14} />)}
    </div>
  );
}

function NodeDetailPanel({
  projectId,
  nodeId,
  editable,
  nodes,
  links,
  childrenOf,
  onSelect,
  onOpenGraph,
}: {
  projectId: string;
  nodeId: string;
  editable: boolean;
  nodes: PlanNode[];
  links: PlanLink[];
  childrenOf: Map<string, PlanNode[]>;
  onSelect: (id: string) => void;
  onOpenGraph: () => void;
}) {
  const { data: node, isLoading, error } = usePlanNode(projectId, nodeId);
  const {
    data: testsData,
    isLoading: testsLoading,
    isError: testsError,
  } = usePlanTests(projectId, nodeId);
  const saveContract = useUpdatePlanContract(projectId, nodeId);
  const saveCriteria = useUpdatePlanCriteria(projectId, nodeId);
  const ratify = useRatifyPlanNode(projectId);
  const transition = useTransitionPlanNode(projectId);
  const move = useMovePlanNode(projectId);
  const {
    data: events,
    isLoading: eventsLoading,
    isError: eventsError,
  } = usePlanNodeEvents(projectId, nodeId);

  const [mode, setMode] = useState<"item" | "impl">("item");
  const [assumptions, setAssumptions] = useState("");
  const [guarantees, setGuarantees] = useState("");
  const [criteria, setCriteria] = useState("");
  const [acceptance, setAcceptance] = useState("");
  const [methodology, setMethodology] = useState<TestMethodology>("unit");

  // Re-seed the editors only when a DIFFERENT node is selected — not on every
  // updated_at bump. The contract and criteria cards are edited and saved
  // independently; re-seeding on each save would let saving one card clobber
  // unsaved edits in the sibling card. (`node?.id` is stable across a node's own
  // revisions; the read-only frozen views below always render fresh server data.)
  useEffect(() => {
    if (!node) return;
    setAssumptions((node.contract?.assumptions ?? []).join("\n"));
    setGuarantees((node.contract?.guarantees ?? []).join("\n"));
    setCriteria((node.verification_criteria ?? []).join("\n"));
    setAcceptance((node.acceptance_criteria ?? []).join("\n"));
    setMethodology((node.test_methodology as TestMethodology) ?? "unit");
    ratify.reset();
    transition.reset();
    setMode("item");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.id]);

  if (isLoading) return <PaneLoading label="Loading node…" />;
  if (error || !node)
    return (
      <NotReady title="Couldn't load the node" error={error ?? undefined} />
    );

  const tests = testsData ?? [];
  // Only trust the reconstructed gate once the tests query has actually resolved —
  // otherwise a childless node reads gate-open (empty checks) before we know its
  // test results, wrongly enabling "Mark verified".
  const testsReady = testsData !== undefined;
  const isDraft = node.state === "draft";
  const canEdit = editable && isDraft;
  const frozen = !isDraft;
  const treeNode = nodes.find((n) => n.id === node.id);
  const children = childrenOf.get(node.id) ?? [];
  const gateOpen = testsReady && isGateOpen(children, tests);
  const txReason = ratify.isError
    ? reasonOf(ratify.error)
    : transition.isError
      ? reasonOf(transition.error)
      : null;

  const onTransition = (target: string) => {
    if (target === "ratified") ratify.mutate(node.id);
    else transition.mutate({ nodeId: node.id, target });
  };

  // The node's own subtree, excluded from the parent options below —
  // reparenting under a descendant would create a cycle (PM rejects it anyway).
  const descendantIds = new Set<string>();
  const stack = [node.id];
  while (stack.length) {
    const cur = stack.pop();
    if (cur === undefined) break;
    for (const child of childrenOf.get(cur) ?? []) {
      if (!descendantIds.has(child.id)) {
        descendantIds.add(child.id);
        stack.push(child.id);
      }
    }
  }

  const idLabel = `#${node.id.slice(0, 6)}`;
  const versionLabel = node.contract
    ? `contract v${node.contract.version}`
    : "unfrozen";
  const frozenAssumptions =
    node.contract?.frozen_assumptions ?? node.contract?.assumptions ?? [];
  const frozenGuarantees =
    node.contract?.frozen_guarantees ?? node.contract?.guarantees ?? [];

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          padding: "20px 22px 48px",
          maxWidth: 760,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {/* Header — kind tile + serif title + state + sub-line */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <KindTile kind={node.kind} size={42} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 11,
                flexWrap: "wrap",
              }}
            >
              <h1
                className="serif"
                style={{
                  fontSize: 23,
                  lineHeight: 1.1,
                  color: "var(--ink)",
                  margin: 0,
                }}
              >
                {node.name}
              </h1>
              <StateChip state={node.state} />
            </div>
            <div
              className="mono"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                marginTop: 6,
                fontSize: 11.5,
                color: "var(--ink-soft)",
                flexWrap: "wrap",
              }}
            >
              <span>{node.kind}</span>
              <span>·</span>
              <span>{idLabel}</span>
              <span>·</span>
              <span>{versionLabel}</span>
            </div>
          </div>
        </div>

        {node.description && (
          <p
            style={{
              fontSize: 13,
              lineHeight: 1.55,
              color: "var(--ink-90)",
              margin: 0,
            }}
          >
            {node.description}
          </p>
        )}

        {/* Item / Implementation toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <ViewToggle mode={mode} onChange={setMode} />
          {mode === "impl" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                color: "var(--ink-mute)",
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: 999,
                  background: "var(--ink-soft)",
                }}
              />
              sandbox · idle
            </span>
          )}
        </div>

        {mode === "impl" ? (
          <ImplementationView node={node} />
        ) : (
          <>
            <NodeStateStepper state={node.state} />

            <GateHero
              childNodes={children}
              tests={tests}
              onSelectChild={onSelect}
            />

            {/* Reparent (draft only) */}
            {canEdit && nodes.length > 1 && (
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={fieldLabel}>Parent</span>
                <select
                  value={treeNode?.parent_id ?? ""}
                  disabled={move.isPending}
                  onChange={(e) =>
                    move.mutate({
                      nodeId: node.id,
                      new_parent_id: e.target.value || null,
                    })
                  }
                  style={{ ...areaStyle, resize: undefined, maxWidth: 260 }}
                >
                  <option value="">— root —</option>
                  {nodes
                    .filter((n) => n.id !== node.id && !descendantIds.has(n.id))
                    .map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name}
                      </option>
                    ))}
                </select>
              </label>
            )}

            {/* Contract */}
            <Card
              label="Contract"
              aside={
                <>
                  <FrozenChip frozen={frozen} />
                  <span
                    className="mono"
                    style={{
                      marginLeft: "auto",
                      fontSize: 10,
                      color: "var(--ink-soft)",
                    }}
                  >
                    {versionLabel}
                  </span>
                </>
              }
            >
              {canEdit ? (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 10 }}
                >
                  <ListField
                    label="Assumptions"
                    value={assumptions}
                    onChange={setAssumptions}
                    disabled={false}
                  />
                  <ListField
                    label="Guarantees"
                    value={guarantees}
                    onChange={setGuarantees}
                    disabled={false}
                  />
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
                </div>
              ) : (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 14 }}
                >
                  <div>
                    <div className="label" style={{ marginBottom: 7 }}>
                      Assumes
                    </div>
                    <BulletList items={frozenAssumptions} variant="assume" />
                  </div>
                  <div>
                    <div className="label" style={{ marginBottom: 7 }}>
                      Guarantees
                    </div>
                    <BulletList items={frozenGuarantees} variant="guarantee" />
                  </div>
                </div>
              )}
            </Card>

            {/* Verification criteria */}
            <Card
              label="Verification criteria"
              aside={<FrozenChip frozen={frozen} />}
            >
              {canEdit ? (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 10 }}
                >
                  <ListField
                    label="Definition of done"
                    value={criteria}
                    onChange={setCriteria}
                    disabled={false}
                  />
                  <ListField
                    label="Acceptance criteria"
                    value={acceptance}
                    onChange={setAcceptance}
                    disabled={false}
                  />
                  <label
                    style={{ display: "flex", flexDirection: "column", gap: 4 }}
                  >
                    <span style={fieldLabel}>Test methodology</span>
                    <select
                      value={methodology}
                      onChange={(e) =>
                        setMethodology(e.target.value as TestMethodology)
                      }
                      style={{ ...areaStyle, resize: undefined, maxWidth: 200 }}
                    >
                      {METHODOLOGIES.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </label>
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
                </div>
              ) : (
                <CriteriaReadView
                  methodology={node.test_methodology}
                  criteria={
                    node.frozen_verification_criteria ??
                    node.verification_criteria
                  }
                  acceptance={node.acceptance_criteria}
                />
              )}
            </Card>

            <NodeTests
              projectId={projectId}
              nodeId={node.id}
              tests={tests}
              loading={testsLoading}
              error={testsError}
              canEdit={canEdit}
              canRun={editable}
            />

            <NodeLinksCard
              nodeId={node.id}
              nodes={nodes}
              links={links}
              onSelect={onSelect}
              onOpenGraph={onOpenGraph}
            />

            {editable && (
              <TransitionBar
                state={node.state}
                gateOpen={gateOpen}
                onTransition={onTransition}
                pending={ratify.isPending || transition.isPending}
                reason={txReason}
              />
            )}

            {/* History */}
            <Card
              label="Activity & decisions"
              aside={
                <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>
                  append-only ledger
                </span>
              }
            >
              {(events ?? []).length === 0 ? (
                <span
                  style={{
                    fontSize: 12,
                    color: eventsError
                      ? "var(--state-failed)"
                      : "var(--ink-mute)",
                  }}
                >
                  {eventsError
                    ? "Couldn't load the history — the planning service may be unavailable."
                    : eventsLoading
                      ? "Loading history…"
                      : "No events yet."}
                </span>
              ) : (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 8 }}
                >
                  {(events ?? []).slice(0, 12).map((e) => (
                    <div
                      key={e.id}
                      style={{
                        display: "flex",
                        gap: 8,
                        fontSize: 12,
                        color: "var(--ink-soft)",
                      }}
                    >
                      <span
                        style={{
                          color: "var(--ink-mute)",
                          fontSize: 10.5,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {eventStamp(e.created_at)}
                      </span>
                      <span
                        style={{ flex: 1, minWidth: 0, color: "var(--ink-90)" }}
                      >
                        {eventLabel(e)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

function CriteriaReadView({
  methodology,
  criteria,
  acceptance,
}: {
  methodology: string | null;
  criteria: string[];
  acceptance: string[];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
      {methodology && (
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span className="label">Method</span>
          <span
            className="mono"
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 6,
              background: tint("var(--ink)", 7),
              color: "var(--ink-mute)",
              fontWeight: 500,
            }}
          >
            {methodology}
          </span>
        </div>
      )}
      {criteria.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {criteria.map((cr, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                fontSize: 12.5,
                color: "var(--ink-90)",
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 10,
                  color: "#c074b0",
                  background: tint("#c074b0", 14),
                  borderRadius: 5,
                  padding: "1px 5px",
                  marginTop: 1,
                  flex: "none",
                  fontWeight: 600,
                }}
              >
                {i + 1}
              </span>
              <span>{cr}</span>
            </div>
          ))}
        </div>
      )}
      {acceptance.length > 0 && (
        <div>
          <div className="label" style={{ marginBottom: 7 }}>
            Acceptance
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {acceptance.map((ac, i) => (
              <span
                key={i}
                style={{
                  fontSize: 11.5,
                  padding: "3px 9px",
                  border: "1px solid var(--border)",
                  borderRadius: 7,
                  background: "var(--surface-2)",
                  color: "var(--ink-mute)",
                }}
              >
                {ac}
              </span>
            ))}
          </div>
        </div>
      )}
      {criteria.length === 0 && acceptance.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>
          No criteria recorded.
        </div>
      )}
    </div>
  );
}

function NodeRow({
  node,
  childNodes,
  selected,
  onSelect,
}: {
  node: PlanNode;
  childNodes: PlanNode[];
  selected: boolean;
  onSelect: () => void;
}) {
  const hasChildren = childNodes.length > 0;
  const verifiedChildren = childNodes.filter(
    (c) => c.state === "verified",
  ).length;
  const rollupPct = hasChildren
    ? (verifiedChildren / childNodes.length) * 100
    : 0;
  const locked =
    node.state === "in_verification" &&
    hasChildren &&
    verifiedChildren < childNodes.length;
  const heavyKind = node.kind === "app" || node.kind === "component";

  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        width: "100%",
        textAlign: "left",
        padding: "8px 12px",
        paddingLeft: 12 + node.depth * 16,
        border: "none",
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
          width: 7,
          height: 7,
          borderRadius: 2,
          background: KIND_COLOR[node.kind],
          flex: "none",
        }}
      />
      <span
        style={{
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          flex: 1,
          gap: 1,
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: heavyKind ? 600 : 400,
            color: "var(--ink)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {node.name}
        </span>
        <span
          className="label"
          style={{ fontSize: 9, color: "var(--ink-soft)" }}
        >
          {KIND_ABBR[node.kind]}
        </span>
      </span>
      {hasChildren && (
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            flex: "none",
          }}
        >
          <MiniBar pct={rollupPct} width={30} />
          <span
            className="mono"
            style={{ fontSize: 10, color: "var(--ink-soft)", minWidth: 22 }}
          >
            {verifiedChildren}/{childNodes.length}
          </span>
        </span>
      )}
      {locked && (
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
      <span style={{ flex: "none" }}>
        <StateChip state={node.state} style={{ fontSize: 9 }} />
      </span>
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
  const [view, setView] = useState<PlanView>("tree");

  const nodes = data?.nodes ?? [];

  // Direct children of each node — drives the tree roll-up bars and the gate.
  const childrenOf = useMemo(() => {
    const m = new Map<string, PlanNode[]>();
    for (const n of nodes) {
      if (n.parent_id) m.set(n.parent_id, [...(m.get(n.parent_id) ?? []), n]);
    }
    return m;
  }, [nodes]);

  // The PM service returns nodes in mutation order, not tree order — so a freshly
  // edited child can drift away from its parent. Re-sort into DFS pre-order
  // (parents immediately above their subtree) so the depth-indented tree reads as
  // a hierarchy. Any node whose parent isn't in the set is treated as a root.
  const orderedNodes = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    const out: PlanNode[] = [];
    const seen = new Set<string>();
    const visit = (n: PlanNode) => {
      if (seen.has(n.id)) return;
      seen.add(n.id);
      out.push(n);
      for (const c of childrenOf.get(n.id) ?? []) visit(c);
    };
    for (const n of nodes) {
      if (!n.parent_id || !ids.has(n.parent_id)) visit(n);
    }
    for (const n of nodes) visit(n); // safety: pick up any cycle-orphaned nodes
    return out;
  }, [nodes, childrenOf]);

  const ratio = useMemo(
    () => verifiedRatio(nodes.map((n) => n.state)),
    [nodes],
  );

  if (isLoading) return <PaneLoading label="Opening the plan…" />;
  if (error) {
    return isNotImplemented(error) ? (
      <NotReady title="Planning isn't live yet" error={error} />
    ) : (
      <NotReady title="Couldn't load the plan" error={error} />
    );
  }
  if (!data) return <PaneLoading label="Opening the plan…" />;

  const { links } = data;
  const editable = project.phase === "PLAN";

  // A plan is ready to approve only once every node has been frozen — ratified or
  // beyond. Approving with a draft (or invalidated/failed) node would advance to
  // code generation on an unverified definition of done, defeating the gate.
  const planReady =
    nodes.length > 0 && nodes.every((n) => RATIFIED_OR_BEYOND.has(n.state));

  const selectNode = (id: string) => {
    setSelected(id);
    setView("tree");
  };

  const addNode = () => {
    const trimmed = name.trim();
    if (!trimmed || createNode.isPending) return;
    createNode.mutate(
      { kind, name: trimmed, parent_id: parentId || null },
      {
        onSuccess: (node) => {
          setName("");
          setSelected(node.id);
        },
      },
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
          <span className="serif" style={{ fontSize: 18 }}>
            Plan
          </span>
          <span style={{ fontSize: 11.5, color: "var(--ink-mute)" }}>
            {nodes.length} node{nodes.length === 1 ? "" : "s"} · {links.length}{" "}
            link
            {links.length === 1 ? "" : "s"}
            {!editable && " · read-only"}
          </span>
        </div>
        <ViewTabs view={view} onChange={setView} />
        {editable && (
          <Button
            onClick={() => approve.mutate()}
            disabled={approve.isPending || !planReady}
            title={
              nodes.length === 0
                ? "Add at least one node before approving"
                : !planReady
                  ? "Every node must be ratified before the plan can be approved"
                  : "Approve the plan and move to code generation"
            }
          >
            {approve.isPending ? "Approving…" : "Approve plan"}
          </Button>
        )}
      </header>

      {view === "graph" ? (
        <PlanGraph
          projectId={project.id}
          nodes={nodes}
          links={links}
          editable={editable}
          selectedId={selected}
          onSelect={selectNode}
        />
      ) : view === "ledger" ? (
        <PlanLedger projectId={project.id} />
      ) : (
        <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
          {/* Tree (master) */}
          <div
            style={{
              width: 340,
              flexShrink: 0,
              borderRight: "1px solid var(--border)",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              background: "var(--paper)",
            }}
          >
            {/* Verified-progress hero */}
            <div
              style={{
                padding: "16px 18px 14px",
                borderBottom: "1px solid var(--border)",
                flex: "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 10,
                }}
              >
                <h2 className="label">Verification tree</h2>
                <span
                  className="mono"
                  style={{ fontSize: 11, color: "var(--ink-soft)" }}
                >
                  {ratio.total} node{ratio.total === 1 ? "" : "s"}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <span
                  className="serif"
                  style={{ fontSize: 30, lineHeight: 1, color: "var(--ink)" }}
                >
                  {ratio.verified}
                </span>
                <span style={{ fontSize: 13, color: "var(--ink-mute)" }}>
                  of {ratio.total} verified
                </span>
                <span
                  className="mono"
                  style={{
                    marginLeft: "auto",
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--state-verified)",
                  }}
                >
                  {ratio.pct}%
                </span>
              </div>
              <MiniBar pct={ratio.pct} width="100%" height={6} />
            </div>

            {/* Rows */}
            <div style={{ flex: 1, overflowY: "auto", padding: "6px 0 16px" }}>
              {nodes.length === 0 ? (
                <div style={{ paddingTop: 40 }}>
                  <EmptyHint
                    title="An empty tree"
                    sub="Add the top-level node to start planning the build."
                  />
                </div>
              ) : (
                orderedNodes.map((node) => (
                  <NodeRow
                    key={node.id}
                    node={node}
                    childNodes={childrenOf.get(node.id) ?? []}
                    selected={selected === node.id}
                    onSelect={() => setSelected(node.id)}
                  />
                ))
              )}
            </div>
          </div>

          {/* Detail */}
          <div
            style={{ flex: 1, minWidth: 0, background: "var(--paper-deep)" }}
          >
            {selected ? (
              <NodeDetailPanel
                key={selected}
                projectId={project.id}
                nodeId={selected}
                editable={editable}
                nodes={nodes}
                links={links}
                childrenOf={childrenOf}
                onSelect={selectNode}
                onOpenGraph={() => setView("graph")}
              />
            ) : (
              <div style={{ paddingTop: 80 }}>
                <EmptyHint
                  title="Select a node"
                  sub="Pick a node to see its contract, criteria, and the roll-up gate."
                />
              </div>
            )}
          </div>
        </div>
      )}

      {editable && view === "tree" && (
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
          <Button
            onClick={addNode}
            disabled={!name.trim() || createNode.isPending}
          >
            Add
          </Button>
        </footer>
      )}
    </div>
  );
}
