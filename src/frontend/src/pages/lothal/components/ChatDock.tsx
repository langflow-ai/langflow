// The chat input dock: a themed auto-growing textarea plus a send control.
// Enter sends, Shift+Enter inserts a newline. Free-text is always available
// here — the clarification chips above are an accelerator, not a replacement.

import { useLayoutEffect, useRef } from "react";

function SendGlyph({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M2.5 8h9M8 4.5 11.5 8 8 11.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ChatDock({
  value,
  onChange,
  onSend,
  disabled,
  placeholder = "Describe what you want to build…",
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /** Disables the send affordance (e.g. while a reply is in flight). */
  disabled?: boolean;
  placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0 && !disabled;

  // Auto-grow to fit the content, capped so it never eats the thread.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        background: "var(--paper)",
        padding: "12px var(--pad) 14px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 8,
          padding: 8,
          background: "var(--surface)",
          border: "1px solid var(--border-strong)",
          borderRadius: 12,
        }}
      >
        <textarea
          ref={ref}
          rows={1}
          aria-label="Message"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
          style={{
            flex: 1,
            resize: "none",
            border: "none",
            outline: "none",
            background: "transparent",
            color: "var(--ink)",
            fontFamily: "var(--sans)",
            fontSize: 14,
            lineHeight: 1.5,
            maxHeight: 160,
            padding: "4px 4px",
          }}
        />
        <button
          type="button"
          aria-label="Send"
          disabled={!canSend}
          onClick={onSend}
          style={{
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 34,
            height: 34,
            borderRadius: 9,
            border: "1px solid transparent",
            background: canSend ? "var(--accent)" : "var(--surface-2)",
            color: canSend ? "var(--accent-fg)" : "var(--ink-soft)",
            cursor: canSend ? "pointer" : "not-allowed",
            transition: "background .15s ease, color .15s ease",
          }}
        >
          <SendGlyph />
        </button>
      </div>
      <p
        className="mono"
        style={{ marginTop: 8, fontSize: 10.5, color: "var(--ink-soft)" }}
      >
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
}
