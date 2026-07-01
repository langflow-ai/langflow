// Phase progress indicator. Three interchangeable styles (the design exposes
// this as a tweak): "stepper" (default), "pill", and "breadcrumb".

import { Fragment } from "react";
import { PHASES, phaseIndex } from "./phases";
import { StatusDot } from "./StatusDot";

export type PhaseStepperStyle = "stepper" | "pill" | "breadcrumb";

export function PhaseStepper({
  phase,
  variant = "stepper",
  currentPhase,
  onSelect,
}: {
  /** The highlighted (active / viewed) phase. */
  phase: string;
  variant?: PhaseStepperStyle;
  /**
   * The project's real phase — drives the "done" checks, the navigable bound,
   * and the "live" marker. Defaults to `phase` (the legacy single-phase use).
   */
  currentPhase?: string;
  /**
   * When provided, the default stepper renders each phase up to `currentPhase`
   * as a button that calls this to navigate (view that phase's artifacts).
   */
  onSelect?: (phaseId: string) => void;
}) {
  const idx = phaseIndex(phase);
  // The farthest reached phase: drives completion + the clickable bound.
  const cur = currentPhase != null ? phaseIndex(currentPhase) : idx;

  if (variant === "pill") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "5px 10px 5px 8px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 999,
          fontSize: 12,
        }}
      >
        <StatusDot phase={phase} />
        <span style={{ color: "var(--ink-soft)" }}>·</span>
        <span
          className="mono"
          style={{ fontSize: 11, color: "var(--ink-soft)" }}
        >
          {String(idx + 1).padStart(2, "0")} /{" "}
          {String(PHASES.length).padStart(2, "0")}
        </span>
      </div>
    );
  }

  if (variant === "breadcrumb") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          color: "var(--ink-soft)",
        }}
      >
        {PHASES.map((p, i) => (
          <Fragment key={p.id}>
            <span
              style={{
                color:
                  i === idx
                    ? "var(--ink)"
                    : i < idx
                      ? "var(--ink-mute)"
                      : "var(--ink-faint)",
                fontWeight: i === idx ? 500 : 400,
              }}
            >
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <span style={{ color: "var(--ink-faint)" }}>›</span>
            )}
          </Fragment>
        ))}
      </div>
    );
  }

  // default: stepper
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 0 }}>
      {PHASES.map((p, i) => {
        // `done` tracks the project's real progress (cur); `active` is the
        // highlighted/viewed step. They coincide in the legacy single-phase use.
        const done = i < cur;
        const active = i === idx;
        const isLive = i === cur;
        const navigable = !!onSelect && i <= cur;
        const Step = navigable ? "button" : "div";
        return (
          <Fragment key={p.id}>
            <Step
              type={navigable ? "button" : undefined}
              onClick={navigable ? () => onSelect?.(p.id) : undefined}
              title={navigable ? `View the ${p.label} stage` : undefined}
              style={{
                position: "relative",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 9px",
                borderRadius: 7,
                background: active ? "var(--surface)" : "transparent",
                border: active
                  ? "1px solid var(--border-strong)"
                  : "1px solid transparent",
                cursor: navigable ? "pointer" : "default",
                font: "inherit",
                color: "inherit",
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 10,
                  color: active
                    ? "var(--accent)"
                    : done
                      ? "var(--ink-soft)"
                      : "var(--ink-faint)",
                  fontWeight: 500,
                }}
              >
                {p.short}
              </span>
              <span
                style={{
                  fontSize: 12.5,
                  color: active
                    ? "var(--ink)"
                    : done
                      ? "var(--ink-mute)"
                      : "var(--ink-soft)",
                  fontWeight: active ? 500 : 400,
                }}
              >
                {p.label}
              </span>
              {done && (
                <span style={{ color: "var(--success)", fontSize: 10 }}>✓</span>
              )}
              {/* Mark the project's real phase when you're viewing an earlier one. */}
              {isLive && !active && (
                <span
                  title="Current stage"
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "var(--accent)",
                    marginLeft: 1,
                  }}
                />
              )}
            </Step>
            {i < PHASES.length - 1 && (
              <span
                style={{
                  width: 12,
                  height: 1,
                  background: i < cur ? "var(--ink-faint)" : "var(--border)",
                }}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
