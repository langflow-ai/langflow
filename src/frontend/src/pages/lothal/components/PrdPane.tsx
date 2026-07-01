// The Workspace's right pane during the CLARIFICATION stage (phase-gates). Once
// the clarification loop reaches clarity, the drafted PRD appears HERE on the main
// page — not only in the chat — so the user can review, edit, and iterate the spec
// (by direct text edit or by chatting) and then Approve it to advance to
// ARCHITECTURE. This makes clarification consistent with every later stage: an
// artifact on the main page behind an explicit approve gate.
//
// States:
//   no PRD yet (still clarifying) → a calm "clarifying…" placeholder
//   PRD present, live             → rendered spec + Edit + "Approve & design architecture"
//   editing                       → a textarea over the same spec, Save / Cancel
//   browsed read-only (past phase)→ rendered spec only (no edit/approve)

import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Project } from "@/controllers/API/queries/lothal";
import { useApprovePrd, useUpdatePrd } from "@/controllers/API/queries/lothal";
import { Button } from "./Button";

function Placeholder() {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        padding: "0 32px",
        textAlign: "center",
      }}
    >
      <div style={{ display: "inline-flex", gap: 6 }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="pulse"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--accent)",
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
      <div
        className="serif"
        style={{ fontSize: 20, color: "var(--ink)", fontStyle: "italic" }}
      >
        Clarifying your idea…
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-soft)", maxWidth: 380 }}>
        Answer the questions in the conversation. Once your intent is clear, the
        product spec will appear here to review and approve.
      </div>
    </div>
  );
}

export function PrdPane({ project }: { project: Project }) {
  const prd = project.prd_content?.trim() ? project.prd_content : null;
  // Editing/approving is live only while the project is actually in CLARIFICATION;
  // browsing back from a later stage shows the spec read-only.
  const inClarification = project.phase === "CLARIFICATION";

  const update = useUpdatePrd(project.id);
  const approve = useApprovePrd(project.id);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(prd ?? "");
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-seed the editor when the PRD changes underneath (e.g. a chat refine) — but
  // never while the user is mid-edit, so a background refetch can't clobber
  // unsaved edits.
  useEffect(() => {
    if (!editing) setDraft(prd ?? "");
  }, [prd, editing]);

  // Clear latched state when the workspace switches projects.
  useEffect(() => {
    setEditing(false);
    setApproved(false);
    setError(null);
  }, [project.id]);

  if (!prd) return <Placeholder />;

  const onSave = async () => {
    const content = draft.trim();
    if (!content || update.isPending) return;
    setError(null);
    try {
      await update.mutateAsync(content);
      setEditing(false);
    } catch {
      setError("Couldn’t save the spec — try again.");
    }
  };

  const onApprove = async () => {
    if (approve.isPending || approved) return;
    setError(null);
    try {
      await approve.mutateAsync();
      setApproved(true);
    } catch {
      setError("Couldn’t approve just now — try again.");
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px var(--pad)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span className="label">Product spec</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          {inClarification ? "draft — review & approve" : "approved"}
        </span>
        {inClarification && !editing && (
          <button
            type="button"
            // Once approval is in flight (or done) the spec is frozen — don't let
            // a late Edit reopen the textarea over a stage that's leaving.
            disabled={approve.isPending || approved}
            onClick={() => {
              setDraft(prd);
              setEditing(true);
            }}
            style={{
              marginLeft: "auto",
              border: "1px solid var(--border-strong)",
              background: "var(--surface)",
              color: "var(--ink)",
              borderRadius: 7,
              padding: "4px 10px",
              fontSize: 12,
              cursor: approve.isPending || approved ? "default" : "pointer",
              opacity: approve.isPending || approved ? 0.5 : 1,
            }}
          >
            Edit
          </button>
        )}
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            style={{
              width: "100%",
              height: "100%",
              boxSizing: "border-box",
              resize: "none",
              border: "none",
              outline: "none",
              padding: "16px var(--pad)",
              background: "var(--paper)",
              color: "var(--ink)",
              fontFamily: "var(--mono)",
              fontSize: 13,
              lineHeight: 1.6,
            }}
          />
        ) : (
          <div className="lothal-adr-scroll">
            <article className="lothal-adr">
              <Markdown remarkPlugins={[remarkGfm]}>{prd}</Markdown>
            </article>
          </div>
        )}
      </div>

      {inClarification && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 12,
            padding: "10px var(--pad)",
            borderTop: "1px solid var(--border)",
            background: "var(--paper)",
          }}
        >
          {error && (
            <span style={{ fontSize: 12, color: "var(--warn)" }}>{error}</span>
          )}
          {editing ? (
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  setDraft(prd);
                  setEditing(false);
                  setError(null);
                }}
                disabled={update.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="accent"
                onClick={onSave}
                disabled={update.isPending || !draft.trim()}
              >
                {update.isPending ? "Saving…" : "Save spec"}
              </Button>
            </>
          ) : (
            <>
              <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                Happy with the spec?
              </span>
              <Button
                variant="accent"
                onClick={onApprove}
                disabled={approve.isPending || approved}
              >
                {approve.isPending || approved
                  ? "Approving…"
                  : "Approve & design architecture"}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
