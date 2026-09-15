import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Keep membership/order consistent with the persisted report's citation contract.
export function reportCitations(markdown: string): string[] {
  return [
    ...new Set(
      Array.from(markdown.matchAll(/\[@([^\]\r\n]*)\]/g), (match) => match[1]),
    ),
  ];
}

export function sourceURL(uri: string): string | undefined {
  try {
    const url = new URL(uri);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

type MarkdownNode = {
  type: string;
  value?: string;
  children?: MarkdownNode[];
  url?: string;
};

// Transform text nodes, so code blocks and link destinations are never rewritten.
function citationPlugin(citations: string[]) {
  return () => (tree: MarkdownNode) => {
    function visit(node: MarkdownNode) {
      if (!node.children || node.type === "link" || node.type === "image")
        return;
      node.children = node.children.flatMap((child) => {
        if (child.type !== "text" || !child.value) {
          visit(child);
          return [child];
        }
        const nodes: MarkdownNode[] = [];
        let position = 0;
        for (const match of child.value.matchAll(/\[@([^\]\r\n]*)\]/g)) {
          const start = match.index!;
          if (start > position)
            nodes.push({
              type: "text",
              value: child.value.slice(position, start),
            });
          const number = citations.indexOf(match[1]) + 1;
          nodes.push({
            type: "link",
            url: `#evidence-${number}`,
            children: [{ type: "text", value: `[${number}]` }],
          });
          position = start + match[0].length;
        }
        if (position < child.value.length)
          nodes.push({ type: "text", value: child.value.slice(position) });
        return nodes;
      });
    }
    visit(tree);
  };
}

export function ReportMarkdown({
  markdown,
  onCitation,
}: {
  markdown: string;
  onCitation: (sourceId: string) => void;
}) {
  const { t } = useTranslation();
  const citations = useMemo(() => reportCitations(markdown), [markdown]);
  const plugin = useMemo(() => citationPlugin(citations), [citations]);
  return (
    <Markdown
      skipHtml
      remarkPlugins={[remarkGfm, plugin]}
      className="prose prose-sm max-w-none break-words dark:prose-invert prose-pre:overflow-auto prose-pre:whitespace-pre-wrap"
      components={{
        a: ({ href, children }) => {
          const number = /^#evidence-(\d+)$/.exec(href ?? "")?.[1];
          const sourceId = number ? citations[Number(number) - 1] : undefined;
          if (sourceId !== undefined)
            return (
              <button
                type="button"
                className="rounded-sm px-0.5 font-medium text-accent-indigo-foreground underline decoration-dotted underline-offset-4 hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                aria-label={t("reports.inspectCitation", { number })}
                onClick={() => onCitation(sourceId)}
              >
                {children}
              </button>
            );
          const url = sourceURL(href ?? "");
          return url ? (
            <a href={url} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ) : (
            <span>{children}</span>
          );
        },
        // A report should not contact external image hosts when it is opened.
        img: ({ alt }) => <span>{alt}</span>,
        table: ({ children }) => (
          <div className="overflow-x-auto">
            <table>{children}</table>
          </div>
        ),
      }}
    >
      {markdown}
    </Markdown>
  );
}
