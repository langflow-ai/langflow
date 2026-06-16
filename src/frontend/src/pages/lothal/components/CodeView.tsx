// The code surface (Story B.5) — the right pane once Lothal has generated the
// scaffold. A self-contained, themed mini-IDE: a file tree built from the flat
// `path` list, editor tabs, lightweight syntax highlighting (see ./syntax), a
// commit strip summarizing the generation, and delivery buttons.
//
// It is presentational: it takes the `/code` payload (`{ path, content }[]`) and
// renders it. The delivery buttons (ZIP / GitHub) are a visual port — ZIP's
// `/download` endpoint is still a 501 stub and GitHub push is post-MVP, so both
// are rendered disabled. They light up in Epic 5 with no change to this view.

import {
  type CSSProperties,
  type ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";
import { highlightTokens, languageFromPath, type TokenType } from "./syntax";

type FileEntry = { path: string; content: string };

// --- file tree model ---------------------------------------------------------

type TreeNode = {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
};

// Build a nested folder/file tree from flat paths, folders before files and
// alphabetical within each level. A segment can be both a file and a directory
// prefix simultaneously (e.g. files ["app", "app/main.py"]); we create two
// distinct sibling nodes in that case so React keys remain unique.
function buildTree(files: FileEntry[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", isDir: true, children: [] };
  for (const file of files) {
    const parts = file.path.split("/").filter(Boolean);
    let node = root;
    parts.forEach((part, i) => {
      const isLeaf = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join("/");
      // Match by name AND the expected isDir value so a file and a directory
      // that share the same path prefix can coexist as separate siblings.
      let child = node.children.find(
        (c) => c.name === part && c.isDir === !isLeaf,
      );
      if (!child) {
        child = { name: part, path, isDir: !isLeaf, children: [] };
        node.children.push(child);
      }
      node = child;
    });
  }
  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) =>
      a.isDir === b.isDir ? a.name.localeCompare(b.name) : a.isDir ? -1 : 1,
    );
    for (const n of nodes) if (n.isDir) sort(n.children);
  };
  sort(root.children);
  return root.children;
}

// First leaf in tree (DFS) order — the file shown by default.
function firstLeaf(nodes: TreeNode[]): string | null {
  for (const n of nodes) {
    if (!n.isDir) return n.path;
    const found = firstLeaf(n.children);
    if (found) return found;
  }
  return null;
}

// --- glyphs ------------------------------------------------------------------

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      aria-hidden
      style={{
        transform: open ? "rotate(90deg)" : "none",
        transition: "transform .12s ease",
        flexShrink: 0,
      }}
    >
      <path
        d="M3.5 2.5 6.5 5l-3 2.5"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FileGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
      <path
        d="M3 1.5h3.5L9.5 4.5V10a.5.5 0 0 1-.5.5H3a.5.5 0 0 1-.5-.5V2a.5.5 0 0 1 .5-.5Z"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <path
        d="M6.5 1.5V4a.5.5 0 0 0 .5.5h2.5"
        stroke="currentColor"
        strokeWidth="1"
      />
    </svg>
  );
}

function FolderGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
      <path
        d="M1.5 3a.5.5 0 0 1 .5-.5h2.2l1 1.2h4.8a.5.5 0 0 1 .5.5V9a.5.5 0 0 1-.5.5H2A.5.5 0 0 1 1.5 9V3Z"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DownloadGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path
        d="M7 2v6.5M4.5 6 7 8.5 9.5 6M3 11h8"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function GitHubGlyph() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

function CheckGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path
        d="M3 7.5 6 10.5l5-6.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden>
      <path
        d="m2.5 2.5 5 5m0-5-5 5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

// --- file tree ---------------------------------------------------------------

function TreeRow({
  node,
  depth,
  activePath,
  collapsed,
  onSelect,
  onToggle,
}: {
  node: TreeNode;
  depth: number;
  activePath: string | null;
  collapsed: Set<string>;
  onSelect: (path: string) => void;
  onToggle: (path: string) => void;
}) {
  const isOpen = !collapsed.has(node.path);
  const isActive = !node.isDir && node.path === activePath;
  const pad = 8 + depth * 13;

  return (
    <>
      <button
        type="button"
        onClick={() => (node.isDir ? onToggle(node.path) : onSelect(node.path))}
        aria-current={isActive ? "true" : undefined}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          width: "100%",
          height: 27,
          paddingLeft: pad,
          paddingRight: 8,
          border: "none",
          background: isActive ? "var(--accent-soft)" : "transparent",
          color: isActive ? "var(--accent-ink)" : "var(--ink-mute)",
          cursor: "pointer",
          fontFamily: "var(--mono)",
          fontSize: 12,
          textAlign: "left",
          borderLeft: isActive
            ? "2px solid var(--accent)"
            : "2px solid transparent",
        }}
      >
        <span
          style={{
            width: 10,
            display: "inline-flex",
            color: "var(--ink-soft)",
          }}
        >
          {node.isDir ? <Chevron open={isOpen} /> : null}
        </span>
        <span
          style={{
            display: "inline-flex",
            color: node.isDir ? "var(--ink-soft)" : "var(--ink-soft)",
          }}
        >
          {node.isDir ? <FolderGlyph /> : <FileGlyph />}
        </span>
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {node.name}
        </span>
      </button>
      {node.isDir && isOpen
        ? node.children.map((child) => (
            <TreeRow
              key={`${child.path}:${child.isDir ? "d" : "f"}`}
              node={child}
              depth={depth + 1}
              activePath={activePath}
              collapsed={collapsed}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))
        : null}
    </>
  );
}

// --- highlighted content -----------------------------------------------------

const TOKEN_COLOR: Record<TokenType, CSSProperties> = {
  comment: { color: "var(--ink-soft)", fontStyle: "italic" },
  string: { color: "var(--success)" },
  keyword: { color: "var(--accent-ink)", fontWeight: 500 },
  number: { color: "var(--warn)" },
  plain: { color: "var(--ink-90)" },
};

const LINE_HEIGHT = "1.6em";

function CodeContent({ file }: { file: FileEntry }) {
  const tokens = useMemo(
    () => highlightTokens(file.content, languageFromPath(file.path)),
    [file.content, file.path],
  );
  const lineCount = useMemo(
    () => file.content.split("\n").length,
    [file.content],
  );

  return (
    <div style={{ flex: 1, overflow: "auto", background: "var(--paper-deep)" }}>
      <div style={{ display: "flex", minWidth: "min-content" }}>
        {/* Line-number gutter — pinned while scrolling horizontally. */}
        <div
          aria-hidden
          className="mono"
          style={{
            position: "sticky",
            left: 0,
            flexShrink: 0,
            padding: "12px 10px",
            textAlign: "right",
            userSelect: "none",
            background: "var(--paper-deep)",
            borderRight: "1px solid var(--border)",
            color: "var(--ink-faint)",
            fontSize: 12.5,
            lineHeight: LINE_HEIGHT,
          }}
        >
          {Array.from({ length: lineCount }, (_, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
        {/* A `<div>` (not `<pre>`): Langflow's global `pre` rule sets a dark
            zinc background with `!important` that an inline style can't beat, so
            it would override the lothal theme. A div with `white-space: pre`
            renders identically without matching that selector. */}
        <div
          className="mono"
          style={{
            margin: 0,
            padding: "12px 16px",
            fontSize: 12.5,
            lineHeight: LINE_HEIGHT,
            whiteSpace: "pre",
            tabSize: 2,
            color: "var(--ink-90)",
          }}
        >
          {tokens.map((t, i) => (
            <span key={i} style={TOKEN_COLOR[t.type]}>
              {t.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- commit / delivery strip -------------------------------------------------

function CommitStrip({ count }: { count: number }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "9px var(--pad)",
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          minWidth: 0,
        }}
      >
        <span style={{ color: "var(--success)", display: "inline-flex" }}>
          <CheckGlyph />
        </span>
        <span className="serif" style={{ fontSize: 16, color: "var(--ink)" }}>
          Generated
        </span>
        <span
          className="mono"
          style={{ fontSize: 11, color: "var(--ink-soft)" }}
        >
          {count} {count === 1 ? "file" : "files"}
        </span>
      </span>
      <span
        style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
        title="Delivery is coming soon"
      >
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <DownloadGlyph />
          Download ZIP
        </Button>
        <Button variant="outline" size="sm" disabled title="Coming soon">
          <GitHubGlyph />
          Push to GitHub
        </Button>
      </span>
    </div>
  );
}

// --- view --------------------------------------------------------------------

export function CodeView({ files }: { files: FileEntry[] }): ReactNode {
  const tree = useMemo(() => buildTree(files), [files]);
  const fileMap = useMemo(
    () => new Map(files.map((f) => [f.path, f.content])),
    [files],
  );
  const defaultPath = useMemo(() => firstLeaf(tree), [tree]);

  const [activePath, setActivePath] = useState<string | null>(null);
  const [openPaths, setOpenPaths] = useState<string[]>([]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  // Tracks an explicit close of the implicit "default" tab so we don't
  // immediately re-open it — closing the sole auto-opened tab should stick.
  const [closedDefault, setClosedDefault] = useState(false);

  // A new file set (e.g. a different project) restores the default-tab behaviour.
  useEffect(() => {
    setClosedDefault(false);
  }, [defaultPath]);

  if (files.length === 0) {
    return (
      <EmptyHint
        title="No files yet"
        sub="Generated files will appear here once the scaffold is built."
      />
    );
  }

  // Resolve the active file, falling back to the first leaf if the stored path
  // is gone (e.g. a different project's payload).
  const activeFile = (() => {
    if (activePath && fileMap.has(activePath)) {
      return { path: activePath, content: fileMap.get(activePath) ?? "" };
    }
    // The user explicitly closed the default tab — don't resurrect it.
    if (!activePath && closedDefault) {
      return null;
    }
    if (defaultPath) {
      return { path: defaultPath, content: fileMap.get(defaultPath) ?? "" };
    }
    return null;
  })();

  // Open tabs: the explicitly-opened files that still exist, always including
  // the active one. Defaults to just the active file on first render.
  const existingOpen = openPaths.filter((p) => fileMap.has(p));
  const tabPaths =
    activeFile && !existingOpen.includes(activeFile.path)
      ? [...existingOpen, activeFile.path]
      : existingOpen.length
        ? existingOpen
        : activeFile
          ? [activeFile.path]
          : [];

  const selectFile = (path: string) => {
    setActivePath(path);
    setOpenPaths((prev) => (prev.includes(path) ? prev : [...prev, path]));
    setClosedDefault(false);
  };

  const closeTab = (path: string) => {
    const next = tabPaths.filter((p) => p !== path);
    setOpenPaths((prev) => prev.filter((p) => p !== path));
    if (activePath === path || (!activePath && activeFile?.path === path)) {
      const fallback = next[next.length - 1] ?? null;
      setActivePath(fallback);
      // Closing the last tab (including the implicit default) leaves none open;
      // remember that so the default tab isn't immediately re-opened.
      if (fallback === null) setClosedDefault(true);
    }
  };

  const toggleFolder = (path: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
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
      <CommitStrip count={files.length} />

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* File tree */}
        <div
          aria-label="File tree"
          style={{
            width: 232,
            flexShrink: 0,
            overflowY: "auto",
            borderRight: "1px solid var(--border)",
            background: "var(--surface)",
            paddingBlock: 8,
          }}
        >
          {tree.map((node) => (
            <TreeRow
              key={`${node.path}:${node.isDir ? "d" : "f"}`}
              node={node}
              depth={0}
              activePath={activeFile?.path ?? null}
              collapsed={collapsed}
              onSelect={selectFile}
              onToggle={toggleFolder}
            />
          ))}
        </div>

        {/* Editor */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Tabs */}
          <div
            role="tablist"
            style={{
              display: "flex",
              alignItems: "stretch",
              overflowX: "auto",
              borderBottom: "1px solid var(--border)",
              background: "var(--paper)",
            }}
          >
            {tabPaths.map((path) => {
              const name = path.split("/").pop() ?? path;
              const isActive = path === activeFile?.path;
              return (
                <div
                  key={path}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    paddingInline: 12,
                    height: 34,
                    flexShrink: 0,
                    borderRight: "1px solid var(--border)",
                    background: isActive ? "var(--paper-deep)" : "transparent",
                    borderBottom: isActive
                      ? "2px solid var(--accent)"
                      : "2px solid transparent",
                  }}
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    onClick={() => setActivePath(path)}
                    className="mono"
                    style={{
                      border: "none",
                      background: "transparent",
                      color: isActive ? "var(--ink)" : "var(--ink-mute)",
                      cursor: "pointer",
                      fontSize: 12,
                      padding: 0,
                    }}
                  >
                    {name}
                  </button>
                  <button
                    type="button"
                    aria-label={`Close ${name}`}
                    onClick={() => closeTab(path)}
                    style={{
                      display: "inline-flex",
                      border: "none",
                      background: "transparent",
                      color: "var(--ink-soft)",
                      cursor: "pointer",
                      padding: 2,
                      borderRadius: 4,
                    }}
                  >
                    <CloseGlyph />
                  </button>
                </div>
              );
            })}
          </div>

          {activeFile ? (
            <CodeContent file={activeFile} />
          ) : (
            <div style={{ flex: 1 }} />
          )}
        </div>
      </div>
    </div>
  );
}
