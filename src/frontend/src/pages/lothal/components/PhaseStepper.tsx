// Phase progress indicator. Three interchangeable styles (the design exposes
// this as a tweak): "stepper" (default), "pill", and "breadcrumb".

import { Fragment } from "react";
import { PHASES, phaseIndex } from "./phases";
import { StatusDot } from "./StatusDot";

export type PhaseStepperStyle = "stepper" | "pill" | "breadcrumb";

export function PhaseStepper({
  phase,
  variant = "stepper",
}: {
  phase: string;
  variant?: PhaseStepperStyle;
}) {
  const idx = phaseIndex(phase);

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
        const done = i < idx;
        const active = i === idx;
        return (
          <Fragment key={p.id}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 9px",
                borderRadius: 7,
                background: active ? "var(--surface)" : "transparent",
                border: active
                  ? "1px solid var(--border-strong)"
                  : "1px solid transparent",
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 10,
                  color: done
                    ? "var(--ink-soft)"
                    : active
                      ? "var(--accent)"
                      : "var(--ink-faint)",
                  fontWeight: 500,
                }}
              >
                {p.short}
              </span>
              <span
                style={{
                  fontSize: 12.5,
                  color: done
                    ? "var(--ink-mute)"
                    : active
                      ? "var(--ink)"
                      : "var(--ink-soft)",
                  fontWeight: active ? 500 : 400,
                }}
              >
                {p.label}
              </span>
              {done && (
                <span style={{ color: "var(--success)", fontSize: 10 }}>✓</span>
              )}
            </div>
            {i < PHASES.length - 1 && (
              <span
                style={{
                  width: 12,
                  height: 1,
                  background: done ? "var(--ink-faint)" : "var(--border)",
                }}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
