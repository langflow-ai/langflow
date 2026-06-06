// A single chat turn. USER bubbles sit right (accent); ASSISTANT bubbles sit
// left (surface). Each carries a small uppercase sender label and fades in.
// `streaming` appends the blinking caret (`.caret`) for an in-flight assistant
// reply. Purely presentational — the Workspace feeds it real message data.

import type { ReactNode } from "react";

export function ChatBubble({
  role,
  content,
  streaming,
  children,
}: {
  role: "USER" | "ASSISTANT";
  content: ReactNode;
  /** Append the blinking caret to an assistant reply still being written. */
  streaming?: boolean;
  /** Optional trailing content rendered under the bubble (e.g. suggestion chips). */
  children?: ReactNode;
}) {
  const isUser = role === "USER";
  return (
    <div
      className="fade-up"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        gap: 5,
      }}
    >
      <span className="label" style={{ fontSize: 9.5, paddingInline: 2 }}>
        {isUser ? "You" : "Lothal"}
      </span>
      <div
        style={{
          maxWidth: "84%",
          padding: "9px 13px",
          fontSize: 14,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          borderRadius: 14,
          ...(isUser
            ? {
                background: "var(--accent)",
                color: "var(--accent-fg)",
                borderBottomRightRadius: 4,
              }
            : {
                background: "var(--surface)",
                color: "var(--ink)",
                border: "1px solid var(--border)",
                borderBottomLeftRadius: 4,
              }),
        }}
      >
        <span className={streaming ? "caret" : undefined}>{content}</span>
      </div>
      {children}
    </div>
  );
}
