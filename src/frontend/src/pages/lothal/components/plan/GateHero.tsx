// The roll-up ratify GATE HERO — a locked/open card that makes the central PLAN
// idea visible: a node verifies only when its own tests pass AND every child is
// verified AND its integration tests pass.
//
// The sub-checks are RECONSTRUCTED client-side from the tree + tests we already
// hold (the ratify endpoint returns only a free-text reason). That server reason
// remains the authoritative verdict and is rendered as an override banner beside
// the transition buttons in PlanPane — this card is the at-a-glance preview.

import type { PlanNode, PlanTest } from "@/controllers/API/queries/lothal";
import { Icon, StateChip } from "./atoms";
import { stateColor, tint } from "./planTheme";

type Check = { label: string; ok: boolean; detail: string };

const OPEN_HUE = "var(--state-verified)";
const LOCKED_HUE = "#cf9a3a";

export function buildGateChecks(
  children: PlanNode[],
  tests: PlanTest[],
): Check[] {
  return buildChecks(children, tests);
}

// Whether the reconstructed roll-up gate is open (no client objection to
// verifying). With checks present, it's open only when every check is green —
// mirroring the locked GateHero card so a disabled "Mark verified" lines up with
// a visible red check. With NO reconstructable checks (a childless leaf with no
// tests), `every` over the empty list is true, so the button stays enabled and
// the server stays the authoritative gate. The server reason is shown regardless.
export function isGateOpen(children: PlanNode[], tests: PlanTest[]): boolean {
  return buildChecks(children, tests).every((c) => c.ok);
}

function buildChecks(children: PlanNode[], tests: PlanTest[]): Check[] {
  const checks: Check[] = [];

  if (children.length > 0) {
    const verified = children.filter((c) => c.state === "verified").length;
    checks.push({
      label: "All children verified",
      ok: verified === children.length,
      detail: `${verified} / ${children.length}`,
    });
  }

  const byScope = (scope: string) => tests.filter((t) => t.scope === scope);
  const passing = (ts: PlanTest[]) =>
    ts.filter((t) => t.latest_status === "passed").length;

  for (const [scope, label] of [
    ["unit", "Unit tests passing"],
    ["integration", "Integration tests passing"],
  ] as const) {
    const ts = byScope(scope);
    if (ts.length > 0) {
      checks.push({
        label,
        ok: passing(ts) === ts.length,
        detail: `${passing(ts)} / ${ts.length}`,
      });
    }
  }

  return checks;
}

export function GateHero({
  childNodes,
  tests,
  onSelectChild,
}: {
  childNodes: PlanNode[];
  tests: PlanTest[];
  onSelectChild: (id: string) => void;
}) {
  const checks = buildChecks(childNodes, tests);
  // Nothing to gate on (a leaf with no tests) — the stepper + transitions carry
  // the state instead of an empty hero.
  if (checks.length === 0) return null;

  const open = checks.every((c) => c.ok);
  const hue = open ? OPEN_HUE : LOCKED_HUE;

  return (
    <div
      style={{
        background: "var(--surface)",
        border: `1px solid ${tint(hue, 35)}`,
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "16px 22px",
          display: "flex",
          alignItems: "center",
          gap: 13,
          background: tint(hue, 8),
          borderBottom: `1px solid ${tint(hue, 35)}`,
        }}
      >
        <span
          style={{
            width: 34,
            height: 34,
            borderRadius: 9,
            background: hue,
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flex: "none",
          }}
        >
          {open ? <Icon.LockOpen size={17} /> : <Icon.Lock size={17} />}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="serif" style={{ fontSize: 18, color: hue }}>
            {open ? "Roll-up gate open" : "Roll-up gate locked"}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-mute)", marginTop: 1 }}>
            {open
              ? "Every precondition is green — this node may roll up to verified."
              : "Verification cannot compose upward until every check below is green."}
          </div>
        </div>
      </div>

      <div style={{ padding: "6px 22px 14px" }}>
        {checks.map((c, i) => {
          const checkHue = c.ok ? OPEN_HUE : "var(--state-failed)";
          return (
            <div
              key={c.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 11,
                padding: "11px 0",
                borderBottom:
                  i < checks.length - 1 ? "1px solid var(--border)" : "none",
              }}
            >
              <span
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 999,
                  flex: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: tint(checkHue, 15),
                  color: checkHue,
                }}
              >
                {c.ok ? <Icon.Check size={12} /> : <Icon.X size={11} />}
              </span>
              <span
                style={{
                  flex: 1,
                  fontSize: 13,
                  color: "var(--ink)",
                  fontWeight: 500,
                }}
              >
                {c.label}
              </span>
              <span
                className="mono"
                style={{ fontSize: 12, fontWeight: 600, color: checkHue }}
              >
                {c.detail}
              </span>
            </div>
          );
        })}

        {childNodes.length > 0 && (
          <div style={{ marginTop: 13 }}>
            <div className="label" style={{ marginBottom: 8 }}>
              Children
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {childNodes.map((ch) => (
                <button
                  key={ch.id}
                  type="button"
                  onClick={() => onSelectChild(ch.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 9,
                    padding: "8px 11px",
                    border: "1px solid var(--border)",
                    borderRadius: 9,
                    cursor: "pointer",
                    background: "var(--paper)",
                    textAlign: "left",
                    width: "100%",
                    color: "var(--ink)",
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 2,
                      background: stateColor(ch.state),
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
                    {ch.name}
                  </span>
                  <StateChip state={ch.state} />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
