import React, { useMemo, useState, useEffect } from "react";
import { highlight, preload, type LighterResult, type Token } from "@code-hike/lighter";

const CODE_HIKE_THEME = "github-dark";

/** Same theme vars Code Hike uses for github-dark so existing CH CSS applies */
const CH_THEME_VARS: React.CSSProperties = {
  ["--ch-t-background" as string]: "#0d1117",
  ["--ch-t-foreground" as string]: "#c9d1d9",
  ["--ch-t-colorScheme" as string]: "dark",
  ["--ch-t-editorLineNumber-foreground" as string]: "#8b949e",
  ["--ch-t-editor-selectionBackground" as string]: "#264f78",
};

type CodeSnippetProps = {
  /** Raw file content (e.g. from !!raw-loader!...) */
  source: string;
  /** Start line (1-based, inclusive) */
  startLine: number;
  /** End line (1-based, inclusive) */
  endLine: number;
  language: string;
  title?: string;
  showLineNumbers?: boolean;
};

function copyToClipboard(text: string): void {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text);
  }
}

/**
 * Renders a slice of a file as a code block using the same highlighter and
 * styling as Code Hike (Markdown ``` blocks), so line-range pulls match the
 * rest of the docs.
 */
export default function CodeSnippet({
  source,
  startLine,
  endLine,
  language,
  title,
  showLineNumbers = true,
}: CodeSnippetProps): React.ReactElement {
  const { slice } = useMemo(() => {
    const lines = source.split("\n");
    const slice = lines.slice(startLine - 1, endLine).join("\n");
    return { slice };
  }, [source, startLine, endLine]);

  const [highlighted, setHighlighted] = useState<LighterResult | null>(null);
  useEffect(() => {
    let cancelled = false;
    preload([language as Parameters<typeof preload>[0][number]], CODE_HIKE_THEME)
      .then(() => highlight(slice, language as Parameters<typeof highlight>[1], CODE_HIKE_THEME))
      .then((result) => {
        if (!cancelled) setHighlighted(result);
      })
      .catch(() => {
        if (!cancelled) setHighlighted(null);
      });
    return () => {
      cancelled = true;
    };
  }, [slice, language]);

  const [copied, setCopied] = React.useState(false);
  const onCopy = (): void => {
    copyToClipboard(slice);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  const lineNumberWidth = showLineNumbers ? String(endLine).length : 0;

  return (
    <div
      className="ch-codeblock"
      style={{
        marginTop: "1.25em",
        marginBottom: "1.25em",
        borderRadius: 6,
        overflow: "hidden",
        boxShadow: "0 13px 27px -5px rgba(50,50,93,0.25), 0 8px 16px -8px rgba(0,0,0,0.3)",
        ...CH_THEME_VARS,
      }}
    >
      {title && (
        <div
          className="ch-frame-title-bar"
          style={{
            padding: "0.75rem 1rem",
            borderBottom: "1px solid #30363d",
            background: "#161b22",
            color: "#c9d1d9",
          }}
        >
          <div className="ch-frame-middle-bar">{title}</div>
        </div>
      )}
      <div className="ch-code-wrapper" data-ch-measured="true" style={CH_THEME_VARS}>
        <code className="ch-code-scroll-parent" data-ch-lang={language} style={{ display: "block", padding: "1rem" }}>
          {highlighted ? (
            (highlighted.lines as Token[][]).map((lineTokens, i) => (
              <React.Fragment key={i}>
                {showLineNumbers && (
                  <span
                    className="ch-code-line-number"
                    style={{ width: `${lineNumberWidth}ch`, marginRight: "1.5ch", display: "inline-block", textAlign: "right" }}
                  >
                    {startLine + i}
                  </span>
                )}
                {lineTokens.map((token, j) => (
                  <span
                    key={j}
                    style={{
                      color: token.style?.color ?? undefined,
                      fontStyle: token.style?.fontStyle ?? undefined,
                      fontWeight: token.style?.fontWeight ?? undefined,
                    }}
                  >
                    {token.content}
                  </span>
                ))}
                {"\n"}
              </React.Fragment>
            ))
          ) : (
            slice.split("\n").map((line, i) => (
              <React.Fragment key={i}>
                {showLineNumbers && (
                  <span
                    className="ch-code-line-number"
                    style={{ width: `${lineNumberWidth}ch`, marginRight: "1.5ch", display: "inline-block", textAlign: "right" }}
                  >
                    {startLine + i}
                  </span>
                )}
                {line}
                {"\n"}
              </React.Fragment>
            ))
          )}
        </code>
        <button
          type="button"
          title="Copy code"
          className="ch-code-button"
          onClick={onCopy}
          style={{ position: "absolute", top: "10px", right: "10px" }}
        >
          {copied ? (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="1.1em" height="1.1em">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="1.1em" height="1.1em">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
