import React, { useCallback, useState } from "react";
import { Copy as CopyIcon, Check as CheckIcon } from "lucide-react";

function nodeToInlineMarkdown(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent ?? "";
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();

  const childText = Array.from(el.childNodes)
    .map(nodeToInlineMarkdown)
    .join("");

  switch (tag) {
    case "strong":
    case "b":
      return `**${childText}**`;
    case "em":
    case "i":
      return `*${childText}*`;
    case "code":
      return `\`${(el.textContent ?? "").replace(/`/g, "\\`")}\``;
    case "a": {
      const href = el.getAttribute("href") ?? "";
      const text = childText || href;
      return href ? `[${text}](${href})` : text;
    }
    default:
      return childText;
  }
}

function nodeToBlockMarkdown(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent ?? "";
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();

  // Skip non-content elements
  if (tag === "style" || tag === "script") {
    return "";
  }

  const inlineChildren = (): string =>
    Array.from(el.childNodes)
      .map(nodeToInlineMarkdown)
      .join("");

  const blockChildren = (): string =>
    Array.from(el.childNodes)
      .map(nodeToBlockMarkdown)
      .join("");

  switch (tag) {
    case "h1":
      return `# ${inlineChildren()}\n\n`;
    case "h2":
      return `## ${inlineChildren()}\n\n`;
    case "h3":
      return `### ${inlineChildren()}\n\n`;
    case "h4":
      return `#### ${inlineChildren()}\n\n`;
    case "h5":
      return `##### ${inlineChildren()}\n\n`;
    case "h6":
      return `###### ${inlineChildren()}\n\n`;
    case "p":
      return `${inlineChildren()}\n\n`;
    case "pre": {
      const codeEl = el.querySelector("code");
      const codeText = codeEl?.textContent ?? el.textContent ?? "";
      const classAttr = codeEl?.getAttribute("class") ?? "";
      const langMatch = classAttr.match(/language-([a-z0-9]+)/i);
      const lang = langMatch?.[1] ?? "";
      const trimmed = codeText.replace(/\s+$/g, "");
      return `\`\`\`${lang}\n${trimmed}\n\`\`\`\n\n`;
    }
    case "ul": {
      const items = Array.from(el.children)
        .filter((child) => child.tagName.toLowerCase() === "li")
        .map((li) => `- ${nodeToInlineMarkdown(li)}`);
      return items.join("\n") + (items.length ? "\n\n" : "");
    }
    case "ol": {
      const items = Array.from(el.children)
        .filter((child) => child.tagName.toLowerCase() === "li")
        .map((li, idx) => `${idx + 1}. ${nodeToInlineMarkdown(li)}`);
      return items.join("\n") + (items.length ? "\n\n" : "");
    }
    case "blockquote": {
      const text = blockChildren()
        .split("\n")
        .map((line) => (line ? `> ${line}` : ">"))
        .join("\n");
      return `${text}\n\n`;
    }
    case "table": {
      // Minimal table handling: fall back to plain text
      return `${el.innerText}\n\n`;
    }
    case "button":
      // Skip interactive UI buttons like the copy control
      return "";
    case "hr":
      return `---\n\n`;
    default:
      return blockChildren();
  }
}

async function copyCurrentPageAsMarkdown(): Promise<boolean> {
  if (typeof document === "undefined" || typeof window === "undefined") return false;

  const container =
    (document.querySelector(".theme-doc-markdown") as HTMLElement | null) ??
    (document.querySelector("article") as HTMLElement | null) ??
    (document.querySelector("main") as HTMLElement | null);

  if (!container) return false;

  const parts = Array.from(container.childNodes).map(nodeToBlockMarkdown);
  const markdown = parts.join("").replace(/\n{3,}/g, "\n\n").trim() + "\n";

  if (!navigator.clipboard?.writeText) {
    return false;
  }

  await navigator.clipboard.writeText(markdown);
  return true;
}

export function CopyPageButton(): JSX.Element | null {
  const [copied, setCopied] = useState(false);

  const handleClick = useCallback(async () => {
    const ok = await copyCurrentPageAsMarkdown();
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }, []);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "flex-start",
        margin: "0.5rem 0 1.25rem 0",
      }}
    >
      <button
        type="button"
        onClick={handleClick}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
          cursor: "pointer",
          borderRadius: "999px",
          padding: "0.22rem 0.7rem",
          border: "1px solid var(--ifm-color-secondary-dark)",
          backgroundColor: "var(--ifm-background-surface-color)",
          color: "var(--ifm-font-color-base)",
          fontSize: "0.7rem",
        }}
      >
        <span aria-hidden="true" style={{ display: "inline-flex", alignItems: "center" }}>
          {copied ? (
            <CheckIcon size={11} strokeWidth={2} style={{ marginRight: "0.22rem" }} />
          ) : (
            <CopyIcon size={11} strokeWidth={2} style={{ marginRight: "0.22rem" }} />
          )}
        </span>
        <span style={{ fontSize: "0.75rem", fontWeight: 500 }}>
          {copied ? "Copied!" : "Copy page"}
        </span>
      </button>
    </div>
  );
}

