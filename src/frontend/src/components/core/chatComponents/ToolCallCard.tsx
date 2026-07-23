import { useEffect, useState } from "react";
import {
  formatTime,
  formatToolTitle,
} from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import type { ToolContent } from "@/types/chat";
import { cn } from "@/utils/utils";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../ui/accordion";
import ContentDisplay from "./ContentDisplay";
import { getToolStatus, TOOL_STATUS_CLASS } from "./toolStatus";

/** Bordered collapsible card for a single tool call. Matches the
 * assistant-ui / ai-chatbot / CopilotKit / Claude / ChatGPT consensus:
 * header is a clickable row with a status dot, the tool name in
 * medium-weight mono, and a duration on the right. Body holds the args
 * and result via ContentDisplay's tool_use branch.
 *
 * Auto-expands while the tool is running; collapses to header-only once
 * the producer attaches a duration (the resolved state). User can toggle
 * manually either way after that. */
export function ToolCallCard({
  content,
  chatId,
  playgroundPage,
}: {
  content: ToolContent;
  chatId: string;
  playgroundPage?: boolean;
}) {
  const status = getToolStatus(content);
  const dotClass = TOOL_STATUS_CLASS[status];

  const rawTitle = content.header?.title || content.name || "Tool";
  const toolTitle =
    typeof rawTitle === "string" ? formatToolTitle(rawTitle) : rawTitle;
  const toolDuration = content.duration ?? 0;
  const itemKey = chatId;

  // Controlled open state. Radix reads ``defaultValue`` only once at mount,
  // so a card that mounts collapsed and later flips to running (history
  // replay, scrollback) never auto-expands. Drive ``value`` from state and
  // open on the running transition; the deps guard means a user collapse
  // while the tool is still running isn't re-opened on the next render.
  const [value, setValue] = useState(status === "running" ? itemKey : "");
  useEffect(() => {
    if (status === "running") {
      setValue(itemKey);
    }
  }, [status, itemKey]);

  return (
    <Accordion
      type="single"
      collapsible
      value={value}
      onValueChange={setValue}
      className="w-full"
    >
      <AccordionItem
        value={itemKey}
        className="border border-border rounded-lg overflow-hidden bg-background"
      >
        <AccordionTrigger className="hover:bg-muted hover:no-underline px-3 py-2.5">
          <div className="flex items-center justify-between w-full pr-2 gap-3">
            <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
              <span
                data-testid={`tool-status-${status}`}
                aria-label={`Tool ${status}`}
                className={cn(
                  "h-1.5 w-1.5 rounded-full flex-shrink-0",
                  dotClass,
                )}
              />
              <p className="truncate text-sm font-medium font-mono">
                {toolTitle}
              </p>
            </div>
            {toolDuration > 0 && (
              <span className="text-xs text-muted-foreground flex-shrink-0">
                {formatTime(toolDuration, true)}
              </span>
            )}
          </div>
        </AccordionTrigger>
        <AccordionContent className="pt-0">
          <div className="text-sm text-muted-foreground px-4 pb-4">
            <ContentDisplay
              content={content}
              chatId={chatId}
              playgroundPage={playgroundPage}
            />
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
