// Clarification suggestion chips. Rendered from an assistant message's
// `suggestions` field; picking one sends it as a user message. Free-text always
// stays available in the ChatDock, so the chips are an accelerator, never the
// only path (the implicit "Other"). Empty `suggestions` → nothing renders.

import { useState } from "react";

function Chip({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const active = hover && !disabled;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: "6px 12px",
        fontSize: 13,
        fontFamily: "var(--sans)",
        color: active ? "var(--accent-ink)" : "var(--ink)",
        background: active ? "var(--accent-soft)" : "var(--surface)",
        border: `1px solid ${active ? "var(--accent)" : "var(--border-strong)"}`,
        borderRadius: 999,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition:
          "background .12s ease, border-color .12s ease, color .12s ease",
      }}
    >
      {label}
    </button>
  );
}

export function AssistantQuestion({
  suggestions,
  onPick,
  disabled,
}: {
  suggestions: string[];
  onPick: (suggestion: string) => void;
  disabled?: boolean;
}) {
  if (!suggestions.length) return null;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        marginTop: 2,
        maxWidth: "84%",
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {/* LLM-produced suggestions can repeat, so the text alone is not a
            safe key; the index disambiguates duplicates and the text keeps
            chip state from leaking across different suggestion sets. */}
        {suggestions.map((s, i) => (
          <Chip
            key={`${i}-${s}`}
            label={s}
            disabled={disabled}
            onClick={() => onPick(s)}
          />
        ))}
      </div>
      <span style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>
        Pick one, or type your own answer below.
      </span>
    </div>
  );
}
