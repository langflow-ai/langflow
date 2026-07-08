// Per-file inner view (prod_spec.md Part B, Stage 6). Opened by clicking a file in
// the file manager. A *changed* file renders in Monaco's diff editor (before-blob vs
// after-blob); an *unchanged* file renders as a plain read-only Monaco editor of the
// blob at the node head. Mode is decided purely by the file's changed-status from the
// node diff. Everything is read-only — the ReviewPane never edits.

import { DiffEditor, Editor } from "@monaco-editor/react";
import type { NodeDiff } from "@/controllers/API/queries/lothal";
import { useBlob } from "@/controllers/API/queries/lothal";
import { useMonacoTheme } from "./monacoShiki";

// Map a path to a Monaco language id (built-in Monarch grammars). Stage 9 layers
// shiki on top for VS Code-exact themes; this covers common languages out of the box.
const EXT_LANG: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  mts: "typescript",
  cts: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  py: "python",
  json: "json",
  md: "markdown",
  markdown: "markdown",
  css: "css",
  scss: "scss",
  less: "less",
  html: "html",
  yml: "yaml",
  yaml: "yaml",
  sh: "shell",
  bash: "shell",
  go: "go",
  rs: "rust",
  java: "java",
  kt: "kotlin",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  hpp: "cpp",
  cs: "csharp",
  rb: "ruby",
  php: "php",
  sql: "sql",
  toml: "ini",
  ini: "ini",
  xml: "xml",
  svg: "xml",
  dockerfile: "dockerfile",
};

function monacoLang(path: string): string {
  const name = (path.split("/").pop() ?? "").toLowerCase();
  if (name === "dockerfile" || name.endsWith(".dockerfile")) return "dockerfile";
  const ext = name.includes(".") ? name.split(".").pop()! : "";
  return EXT_LANG[ext] ?? "plaintext";
}

const EDITOR_OPTIONS = {
  readOnly: true,
  domReadOnly: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  automaticLayout: true,
  fontSize: 12.5,
  renderWhitespace: "selection",
} as const;

function centered(text: string) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 13,
        color: "var(--ink-soft)",
      }}
    >
      {text}
    </div>
  );
}

export function ReviewFileView({
  projectId,
  nodeId,
  path,
  diff,
}: {
  projectId: string;
  nodeId: string;
  path: string;
  diff: NodeDiff;
}) {
  const meta = diff.files.find((f) => f.path === path);
  const changed = !!meta;
  const isAdded = meta?.status === "added";
  const isDeleted = meta?.status === "deleted";
  const binary = meta?.binary ?? false;
  // The "before" side of a rename lives under the old path.
  const beforePath = meta?.old_path ?? path;

  // after: the blob at the node head (absent for a deleted file).
  const after = useBlob(
    projectId,
    nodeId,
    isDeleted ? null : diff.after,
    isDeleted ? null : path,
  );
  // before: the blob at the branch point (absent for an added file, or an unchanged
  // one — an unchanged file only needs its single current content).
  const before = useBlob(
    projectId,
    nodeId,
    changed && !isAdded ? diff.before : null,
    changed && !isAdded ? beforePath : null,
  );
  // One theme across every per-file editor (shiki VS Code theme once it binds, else
  // Monaco's built-in). Kept above the early returns so hook order is stable.
  const theme = useMonacoTheme();

  if (binary) return centered("Binary file — no text view.");

  const lang = monacoLang(path);

  // Unchanged file → a plain read-only editor of its single content.
  if (!changed) {
    if (after.isLoading) return centered("Loading…");
    if (after.isError || !after.data) return centered("Couldn't load the file.");
    if (after.data.truncated)
      return centered("File too large to display inline.");
    return (
      <Editor
        height="100%"
        theme={theme}
        language={lang}
        value={after.data.content ?? ""}
        options={EDITOR_OPTIONS}
      />
    );
  }

  // Changed file → the before/after diff editor.
  const loading =
    (!isDeleted && after.isLoading) || (!isAdded && before.isLoading);
  if (loading) return centered("Loading…");
  const afterTooBig = !isDeleted && after.data?.truncated;
  const beforeTooBig = !isAdded && before.data?.truncated;
  if (afterTooBig || beforeTooBig)
    return centered("File too large to display inline.");

  const original = isAdded ? "" : (before.data?.content ?? "");
  const modified = isDeleted ? "" : (after.data?.content ?? "");
  return (
    <DiffEditor
      height="100%"
      theme={theme}
      language={lang}
      original={original}
      modified={modified}
      options={{ ...EDITOR_OPTIONS, renderSideBySide: true }}
    />
  );
}
