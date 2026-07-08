// Whole-node diff (prod_spec.md Part B, Stage 4). Feeds the raw unified diff from the
// git-read service into `react-diff-view` for a GitHub-style multi-file view. Each
// file is a collapsible card headed with its change-status, ± line counts, and a
// binary/rename signal; large files auto-collapse so a 50+-file diff never freezes.
//
// Syntax highlighting inside hunks is layered on in Stage 9 (shiki tokens); here the
// diff renders in plain text, which is correct and fast.

import { type ReactNode, useMemo, useState } from "react";
import { Diff, Hunk, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import type { DiffFile, NodeDiff } from "@/controllers/API/queries/lothal";
import { EmptyHint } from "./EmptyHint";

type ParsedFile = ReturnType<typeof parseDiff>[number];

const STATUS_META: Record<string, { label: string; color: string }> = {
  added: { label: "added", color: "var(--success)" },
  modified: { label: "modified", color: "#c08a2e" },
  deleted: { label: "deleted", color: "var(--warn)" },
  renamed: { label: "renamed", color: "#6f5bd0" },
  copied: { label: "copied", color: "#3e7ab8" },
  "type-changed": { label: "type changed", color: "var(--ink-soft)" },
};

// Files with more changed lines than this collapse by default (expand on click), so a
// huge generated-file diff doesn't render thousands of rows up front.
const AUTO_COLLAPSE_LINES = 400;

function Tag({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span
      style={{
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: "0.02em",
        color,
        border: `1px solid color-mix(in srgb, ${color} 45%, transparent)`,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        borderRadius: 5,
        padding: "1px 6px",
        flex: "none",
      }}
    >
      {children}
    </span>
  );
}

function notice(text: string) {
  return (
    <div
      style={{
        padding: "14px 16px",
        fontSize: 12.5,
        color: "var(--ink-soft)",
        fontStyle: "italic",
      }}
    >
      {text}
    </div>
  );
}

function displayPath(file: ParsedFile): string {
  const nw = file.newPath && file.newPath !== "/dev/null" ? file.newPath : null;
  const old = file.oldPath && file.oldPath !== "/dev/null" ? file.oldPath : null;
  if (file.type === "rename" && old && nw) return `${old} → ${nw}`;
  return nw ?? old ?? "(unknown)";
}

function FileDiff({ file, meta }: { file: ParsedFile; meta?: DiffFile }) {
  const additions = meta?.additions ?? 0;
  const deletions = meta?.deletions ?? 0;
  const binary = meta?.binary ?? false;
  const [open, setOpen] = useState(
    !binary && additions + deletions <= AUTO_COLLAPSE_LINES,
  );
  const status = meta?.status ?? file.type;
  const s = STATUS_META[status] ?? { label: status, color: "var(--ink-soft)" };

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 8,
        marginBottom: 12,
        overflow: "hidden",
        background: "var(--paper)",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          width: "100%",
          padding: "8px 12px",
          border: "none",
          borderBottom: open ? "1px solid var(--border)" : "none",
          background: "var(--surface)",
          cursor: "pointer",
          textAlign: "left",
          font: "inherit",
        }}
      >
        <span
          style={{
            transform: open ? "rotate(90deg)" : "none",
            transition: "transform 0.12s",
            color: "var(--ink-soft)",
            fontSize: 10,
            flex: "none",
          }}
        >
          ▶
        </span>
        <span
          className="mono"
          style={{
            fontSize: 12,
            color: "var(--ink)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flex: 1,
          }}
        >
          {displayPath(file)}
        </span>
        {binary && <Tag color="var(--ink-soft)">binary</Tag>}
        {!binary && additions > 0 && (
          <span style={{ fontSize: 11, color: "var(--success)", flex: "none" }}>
            +{additions}
          </span>
        )}
        {!binary && deletions > 0 && (
          <span style={{ fontSize: 11, color: "var(--warn)", flex: "none" }}>
            −{deletions}
          </span>
        )}
        <Tag color={s.color}>{s.label}</Tag>
      </button>
      {open &&
        (binary ? (
          notice("Binary file changed — no text diff to show.")
        ) : file.hunks.length === 0 ? (
          notice("No line changes (mode or metadata only).")
        ) : (
          <div className="review-diff">
            <Diff viewType="unified" diffType={file.type} hunks={file.hunks}>
              {(hunks) =>
                hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)
              }
            </Diff>
          </div>
        ))}
    </div>
  );
}

export function ReviewDiff({ diff }: { diff: NodeDiff }) {
  const files = useMemo(
    () => (diff.unified ? parseDiff(diff.unified) : []),
    [diff.unified],
  );
  // Match each parsed file back to the git-read summary (status/binary/counts) by its
  // new path (or old path for a delete), so the header badges are authoritative.
  const metaByPath = useMemo(() => {
    const m = new Map<string, DiffFile>();
    for (const f of diff.files) m.set(f.path, f);
    return m;
  }, [diff.files]);

  if (diff.empty || (files.length === 0 && diff.files.length === 0)) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
        }}
      >
        <EmptyHint
          title="No changes"
          sub="This node produced no diff — it's metadata-only, or its code hasn't been generated yet."
        />
      </div>
    );
  }

  return (
    <div style={{ padding: 12 }}>
      {diff.truncated && notice("Diff truncated — it's very large. Open individual files for full content.")}
      {files.map((file, i) => {
        const key =
          file.newPath && file.newPath !== "/dev/null"
            ? file.newPath
            : (file.oldPath ?? String(i));
        const metaKey =
          file.newPath && file.newPath !== "/dev/null"
            ? file.newPath
            : (file.oldPath ?? "");
        return <FileDiff key={key} file={file} meta={metaByPath.get(metaKey)} />;
      })}
    </div>
  );
}
