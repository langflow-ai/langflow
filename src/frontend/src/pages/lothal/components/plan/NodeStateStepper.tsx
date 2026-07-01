// The per-node lifecycle stepper (draft → ratified → in progress → in
// verification → verified) plus the guard line that explains the current state's
// gate. Distinct from the top-bar PhaseStepper, which tracks the PROJECT phase.
//
// `state` is a free string on the wire; the UI owns the ordering via STATE_ORDER.
// Off-pipeline states (failed / invalidated) render every step as upcoming — the
// StateChip + guard note carry that meaning instead.

import { Fragment } from "react";
import { Icon } from "./atoms";
import {
  guardOf,
  STATE_ORDER,
  stateColor,
  stateLabel,
  tint,
} from "./planTheme";

function StepDot({
  status,
  hue,
}: {
  status: "done" | "current" | "future";
  hue: string;
}) {
  const base = {
    position: "relative" as const,
    zIndex: 1,
    width: 20,
    height: 20,
    borderRadius: 999,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flex: "none",
  };
  if (status === "done") {
    return (
      <span
        style={{
          ...base,
          background: "var(--state-verified)",
          color: "#fff",
        }}
      >
        <Icon.Check size={12} />
      </span>
    );
  }
  if (status === "current") {
    return (
      <span
        style={{
          ...base,
          background: "var(--surface)",
          border: `2px solid ${hue}`,
          boxShadow: `0 0 0 4px ${tint(hue, 20)}`,
        }}
      />
    );
  }
  return (
    <span
      style={{
        ...base,
        background: "var(--surface)",
        border: "2px solid var(--border-strong)",
      }}
    />
  );
}

export function NodeStateStepper({ state }: { state: string }) {
  const idx = STATE_ORDER.indexOf(state as (typeof STATE_ORDER)[number]);
  const guard = guardOf(state);

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: "18px 22px 16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start" }}>
        {STATE_ORDER.map((s, i) => {
          const status: "done" | "current" | "future" =
            idx >= 0 && i < idx ? "done" : i === idx ? "current" : "future";
          const hue = stateColor(s);
          return (
            <div
              key={s}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                flex: 1,
                position: "relative",
              }}
            >
              {i > 0 && (
                <div
                  style={{
                    position: "absolute",
                    top: 10,
                    right: "50%",
                    width: "100%",
                    height: 2,
                    background:
                      status === "done" || (idx >= 0 && i <= idx)
                        ? "var(--state-verified)"
                        : "var(--border)",
                  }}
                />
              )}
              <StepDot status={status} hue={hue} />
              <span
                style={{
                  marginTop: 8,
                  fontSize: 11,
                  textAlign: "center",
                  color:
                    status === "current"
                      ? "var(--ink)"
                      : status === "done"
                        ? "var(--ink-mute)"
                        : "var(--ink-soft)",
                  fontWeight: status === "current" ? 600 : 400,
                }}
              >
                {stateLabel(s)}
              </span>
            </div>
          );
        })}
      </div>
      <div
        style={{
          marginTop: 14,
          paddingTop: 13,
          borderTop: "1px solid var(--border)",
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
        }}
      >
        <span
          style={{ color: "var(--accent)", flex: "none", marginTop: 1 }}
          aria-hidden
        >
          <Icon.Shield size={14} />
        </span>
        <span
          style={{ fontSize: 12, color: "var(--ink-mute)", lineHeight: 1.5 }}
        >
          <Fragment>
            <b style={{ color: "var(--ink)", fontWeight: 600 }}>
              Guard · {guard.title}
            </b>
            {guard.note ? ` — ${guard.note}` : ""}
          </Fragment>
        </span>
      </div>
    </div>
  );
}
