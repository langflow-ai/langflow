/**
 * Plain prose Markdown wrapper used across the assistant panel for
 * non-rich text (file/flow proposal preambles, plan refining context, etc).
 *
 * For rich rendering that overrides ``code`` / ``a`` components (the agent's
 * primary response body), use the inline `<Markdown>` in
 * `assistant-message-body.tsx` directly — the override list is large enough
 * that a generic wrapper would be more confusing than clarifying.
 */

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CHAT_MARKDOWN_CLASSES =
  "prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1";

export function ChatMarkdown({ children }: { children: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} className={CHAT_MARKDOWN_CLASSES}>
      {children}
    </Markdown>
  );
}
