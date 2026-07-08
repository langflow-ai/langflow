// Highlighting fidelity (prod_spec.md Part B, Stage 9). Binds shiki's VS Code-exact
// grammars + theme into Monaco via `shikiToMonaco`, so the per-file view uses the same
// theme the whole app aims for. This is the "optional upgrade" over Monaco's built-in
// Monarch grammars: it degrades gracefully — if shiki fails to initialize, editors keep
// working on Monaco's built-in `vs` theme, never erroring.
//
// It also points @monaco-editor/react at the bundled monaco-editor (not a CDN), so the
// editor loads on the app's own origin and offline.

import { loader } from "@monaco-editor/react";
import { shikiToMonaco } from "@shikijs/monaco";
import * as monaco from "monaco-editor";
import { useEffect, useState } from "react";
import { createHighlighter } from "shiki";

loader.config({ monaco });

// One theme, applied across every per-file editor (and coherent with the light
// react-diff-view theme used by the whole-node diff).
const SHIKI_THEME = "github-light";
const FALLBACK_THEME = "vs";

// Grammars to preload — the languages the file view maps paths onto (see
// ReviewFileView's EXT_LANG). shikiToMonaco registers each (and its aliases, e.g.
// bash→shell) as a Monaco language; anything unregistered degrades to plain text.
const LANGS = [
  "typescript",
  "tsx",
  "javascript",
  "jsx",
  "python",
  "json",
  "markdown",
  "css",
  "scss",
  "less",
  "html",
  "yaml",
  "bash",
  "go",
  "rust",
  "java",
  "kotlin",
  "c",
  "cpp",
  "csharp",
  "ruby",
  "php",
  "sql",
  "ini",
  "xml",
  "docker",
];

// Initialize shiki once per process and bind it into Monaco. Resolves to whether the
// VS Code theme is available; on any failure it resolves false and callers keep the
// built-in theme.
let shikiPromise: Promise<boolean> | null = null;
function ensureShiki(): Promise<boolean> {
  if (!shikiPromise) {
    shikiPromise = createHighlighter({
      themes: [SHIKI_THEME],
      langs: LANGS,
    })
      .then((highlighter) => {
        shikiToMonaco(highlighter, monaco);
        return true;
      })
      .catch((err) => {
        // Non-fatal: the editor falls back to Monaco's built-in grammars + theme.
        console.warn("shiki init failed; using Monaco built-in highlighting", err);
        return false;
      });
  }
  return shikiPromise;
}

/**
 * The Monaco theme id the per-file editors should use. Starts on the built-in `vs`
 * theme and switches to the VS Code-exact shiki theme once it has bound — so an editor
 * never references an unregistered theme (which Monaco would reject).
 */
export function useMonacoTheme(): string {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let mounted = true;
    void ensureShiki().then((ok) => {
      if (mounted && ok) setReady(true);
    });
    return () => {
      mounted = false;
    };
  }, []);
  return ready ? SHIKI_THEME : FALLBACK_THEME;
}
