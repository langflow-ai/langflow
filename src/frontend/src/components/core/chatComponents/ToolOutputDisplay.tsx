import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import type { JSONValue } from "@/types/chat";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import { cn } from "@/utils/utils";
import { ToolSection } from "./ToolSection";
import {
  isToolMessageEnvelope,
  looksPreformatted,
  unwrapToolMessage,
} from "./toolOutput";

/** Render a single tool output value as the best-fit primitive:
 *   - markdown-y string  -> Markdown renderer (prose)
 *   - pre-formatted text -> SimplifiedCodeTabComponent (text)
 *   - anything else      -> SimplifiedCodeTabComponent (json)
 *
 * Extracted from ContentDisplay so the tabbed envelope visualizer can
 * reuse the same routing for whichever value lives behind a tab. */
function FormattedOutput({ value }: { value: JSONValue }) {
  if (value === null || value === undefined) return null;

  if (typeof value === "string") {
    if (looksPreformatted(value)) {
      return <SimplifiedCodeTabComponent language="text" code={value} />;
    }
    return (
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeMathjax]}
        className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
        components={{
          pre({ node, ...props }) {
            return <>{props.children}</>;
          },
          ol({ node, ...props }) {
            return <ol className="max-w-full">{props.children}</ol>;
          },
          ul({ node, ...props }) {
            return <ul className="max-w-full">{props.children}</ul>;
          },
          code: ({ node, className, children, ...props }) => {
            const content = String(children);
            if (isCodeBlock(className, props, content)) {
              return (
                <SimplifiedCodeTabComponent
                  language={extractLanguage(className)}
                  code={content.replace(/\n$/, "")}
                />
              );
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {value}
      </Markdown>
    );
  }

  try {
    return (
      <SimplifiedCodeTabComponent
        language="json"
        code={JSON.stringify(value, null, 2)}
      />
    );
  } catch {
    return <span>{String(value)}</span>;
  }
}

type Tab = "result" | "metadata";

function isMcpCallToolResultArtifact(
  value: JSONValue | undefined,
): value is Record<string, JSONValue> {
  return (
    value !== null &&
    value !== undefined &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Array.isArray(value.content) &&
    typeof value.isError === "boolean"
  );
}

/** Tab control sized for the inside of a tool-call card. Matches the
 * underline-on-active pattern used across assistant-ui / Claude /
 * ChatGPT — quiet by default, the active tab gets a 2px underline in
 * the primary color. */
function TabButton({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-selected={selected}
      role="tab"
      className={cn(
        "px-1 pb-1.5 -mb-px text-xs font-medium border-b-2 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm",
        selected
          ? "text-primary border-primary"
          : "text-muted-foreground border-transparent hover:text-primary",
      )}
    >
      {children}
    </button>
  );
}

/** Top-level renderer for a tool's output, wrapped in an "Output"
 * eyebrow so the section is unambiguous next to the "Arguments" block
 * above it. Routes by shape:
 *   - LangChain ToolMessage envelope with non-standard metadata keys
 *     (additional_kwargs, response_metadata, type, ...) gets a 2-tab UI:
 *     "Result" prefers the structured `.artifact` and falls back to the
 *     model-facing `.content`. MCP `CallToolResult` artifacts are protocol
 *     envelopes, so their readable content stays in Result and the raw
 *     artifact stays in Metadata. Plumbing keys (name, id, tool_call_id,
 *     status) are suppressed because the accordion trigger surfaces them.
 *   - Anything else (simple string, plain dict, unwrappable envelope)
 *     falls through to FormattedOutput directly under the eyebrow —
 *     no tabs, just the body. */
export function ToolOutputDisplay({ output }: { output: JSONValue }) {
  const [tab, setTab] = useState<Tab>("result");

  if (!isToolMessageEnvelope(output)) {
    return (
      <ToolSection eyebrow="Output">
        <div className="max-h-96 overflow-auto">
          <FormattedOutput value={unwrapToolMessage(output)} />
        </div>
      </ToolSection>
    );
  }

  const artifact = output.artifact;
  const isMcpArtifact = isMcpCallToolResultArtifact(artifact);
  const result = artifact != null && !isMcpArtifact ? artifact : output.content;
  // Strip the standard ToolMessage plumbing keys from the metadata view —
  // the accordion trigger already shows tool name and status, and id /
  // tool_call_id aren't useful in the UI. What remains is the actually
  // interesting custom metadata (additional_kwargs, response_metadata,
  // type, custom fields). Component artifacts are the primary result, while
  // raw MCP protocol artifacts remain metadata behind readable content.
  const metadata = Object.fromEntries(
    Object.entries(output).filter(([key, value]) => {
      if (key === "artifact") return value != null && isMcpArtifact;
      return !TOOL_MESSAGE_KEYS_PLUS_CONTENT.has(key);
    }),
  );
  const hasMetadata = Object.keys(metadata).length > 0;

  // If after stripping plumbing there's no meaningful metadata left,
  // drop the tabs and render the result directly.
  if (!hasMetadata) {
    return (
      <ToolSection eyebrow="Output">
        <FormattedOutput value={result} />
      </ToolSection>
    );
  }

  return (
    <ToolSection eyebrow="Output">
      <div role="tablist" className="flex gap-4 border-b border-border">
        <TabButton selected={tab === "result"} onClick={() => setTab("result")}>
          Result
        </TabButton>
        <TabButton
          selected={tab === "metadata"}
          onClick={() => setTab("metadata")}
        >
          Metadata
        </TabButton>
      </div>
      {/* Stable height envelope: min-h holds the card chrome steady when
       * switching from a short Result tab to a tall Metadata tab (and
       * vice versa), and max-h caps growth so tall metadata scrolls
       * inside instead of pushing everything below the card down.
       * AnimatePresence mode="wait" lets the outgoing tab finish fading
       * before the incoming one paints, so we don't have to absolute-
       * position the layers (which would break the scroll). */}
      <div className="min-h-[180px] max-h-96 overflow-auto">
        <AnimatePresence initial={false} mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.08, ease: "easeOut" }}
          >
            {tab === "result" ? (
              <FormattedOutput value={result} />
            ) : (
              <SimplifiedCodeTabComponent
                language="json"
                code={JSON.stringify(metadata, null, 2)}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </ToolSection>
  );
}

// `content` belongs in the Result tab; the canonical plumbing fields aren't
// worth exposing — keep this set local rather than re-exporting another
// constant. Artifact routing depends on whether it is component data or an
// MCP protocol envelope, so it is handled separately above.
const TOOL_MESSAGE_KEYS_PLUS_CONTENT = new Set([
  "content",
  "name",
  "id",
  "tool_call_id",
  "status",
]);
