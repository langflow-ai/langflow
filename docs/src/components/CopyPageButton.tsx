import React, { useCallback, useEffect, useState } from "react";
import { Copy as CopyIcon, Check as CheckIcon } from "lucide-react";
import styles from "./CopyPageButton.module.css";

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

function isEditableElement(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  return (el as HTMLElement).isContentEditable;
}

export function CopyPageButton(): JSX.Element | null {
  const [copied, setCopied] = useState(false);
  const [isMac, setIsMac] = useState(true);

  const handleCopy = useCallback(async () => {
    const ok = await copyCurrentPageAsMarkdown();
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }, []);

  useEffect(() => {
    const platform =
      (navigator as { userAgentData?: { platform?: string } }).userAgentData
        ?.platform ?? navigator.platform;
    setIsMac(/Mac|iPhone|iPad|iPod/i.test(platform));

    const onKeyDown = (event: KeyboardEvent) => {
      // Option/Alt+C copies the whole page as Markdown. Unlike Cmd/Ctrl+C,
      // this never shadows the native copy gesture or clobbers the clipboard
      // on a reflexive copy with a collapsed selection.
      // event.code is required here: on macOS, Option+C produces
      // event.key === "ç", and key-based checks also break on non-Latin
      // layouts.
      const isCopyShortcut =
        event.altKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        event.code === "KeyC";
      if (!isCopyShortcut) return;
      if (event.repeat) return;

      // Don't fire while typing in a form field, where Option+C may insert a
      // character (e.g. "ç" on macOS).
      if (isEditableElement(document.activeElement)) return;

      event.preventDefault();
      void handleCopy();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleCopy]);

  const shortcutLabel = isMac ? "⌥C" : "Alt+C";

  return (
    <div className={styles.root}>
      <button
        type="button"
        onClick={handleCopy}
        className={styles.button}
        title={`Copy page as Markdown (${shortcutLabel})`}
        aria-keyshortcuts="Alt+C"
      >
        <span aria-hidden="true" className={styles.icon}>
          {copied ? (
            <CheckIcon size={12} strokeWidth={2} />
          ) : (
            <CopyIcon size={12} strokeWidth={2} />
          )}
        </span>
        <span className={styles.label}>{copied ? "Copied!" : "Copy page"}</span>
        <kbd aria-hidden="true" className={styles.kbd}>
          {shortcutLabel}
        </kbd>
      </button>
    </div>
  );
}

