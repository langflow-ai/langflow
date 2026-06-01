"use client";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { BorderTrail } from "@/components/core/border-trail";
import { useToolDurations } from "@/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-tool-durations";
import {
  formatTime,
  formatToolTitle,
} from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import {
  type ContentBlockItem,
  type ContentType,
  isGroupedBlock,
} from "@/types/chat";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../ui/accordion";
import ContentDisplay from "./ContentDisplay";
import DurationDisplay from "./DurationDisplay";
import { groupConsecutiveCitations } from "./groupCitations";
import { SourcesStrip } from "./SourcesStrip";
import { ToolCallCard } from "./ToolCallCard";
import { getToolStatus, TOOL_STATUS_CLASS } from "./toolStatus";

interface ContentBlockDisplayProps {
  contentBlocks: ContentBlockItem[];
  isLoading?: boolean;
  state?: string;
  chatId: string;
  playgroundPage?: boolean;
  hideHeader?: boolean;
}

export function ContentBlockDisplay({
  contentBlocks,
  isLoading,
  state,
  chatId,
  playgroundPage,
  hideHeader = false,
}: ContentBlockDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Separate flat content items from grouped blocks. Memoize so child
  // components (notably Radix Accordion, which collects refs per render)
  // see stable references across re-renders. Without this, every parent
  // render produces fresh filter() arrays, every AccordionItem looks
  // 'new' to the collection, refs are re-registered, and Radix loops
  // until React hits the max-update-depth guard.
  const groupedBlocks = useMemo(
    () => contentBlocks.filter(isGroupedBlock),
    [contentBlocks],
  );
  const flatItems = useMemo(
    () =>
      contentBlocks.filter(
        (item): item is ContentType => !isGroupedBlock(item),
      ),
    [contentBlocks],
  );

  // Use shared hook for tool duration tracking (only grouped blocks)
  const { toolElapsedTimes, toolItems } = useToolDurations(
    groupedBlocks.length > 0 ? groupedBlocks : undefined,
    isLoading ?? false,
  );

  // Stabilize the Radix Accordion defaultValue so the wrapped accordion
  // doesn't see a new array reference on every parent re-render.
  const runningToolKeys = useMemo(
    () =>
      toolItems
        .filter(({ content }) => getToolStatus(content) === "running")
        .map(({ toolKey }) => toolKey),
    [toolItems],
  );

  // Controlled open state for the tools accordion. Radix only reads
  // ``defaultValue`` once at mount, so a tool that mounts or flips to
  // running *after* the first render never auto-expands. Seed with the
  // keys running at mount, then add any key that *newly* enters the
  // running state. We only auto-open on the running transition (diffed
  // against the previous set), never re-open, so a user collapse via
  // ``onValueChange`` stays collapsed even while the tool is still running.
  const [openToolKeys, setOpenToolKeys] = useState<string[]>(runningToolKeys);
  const prevRunningKeysRef = useRef<string[]>(runningToolKeys);
  useEffect(() => {
    const newlyRunning = runningToolKeys.filter(
      (key) => !prevRunningKeysRef.current.includes(key),
    );
    if (newlyRunning.length > 0) {
      setOpenToolKeys((prev) =>
        Array.from(new Set([...prev, ...newlyRunning])),
      );
    }
    prevRunningKeysRef.current = runningToolKeys;
  }, [runningToolKeys]);

  if (!toolItems.length && !flatItems.length) {
    return null;
  }

  const totalDuration = isLoading
    ? undefined
    : toolItems.reduce((acc, { content, toolKey }) => {
        const toolDuration = toolElapsedTimes[toolKey] ?? content.duration ?? 0;
        return acc + toolDuration;
      }, 0);

  if (!contentBlocks?.length) {
    return null;
  }

  const headerIcon = state === "partial" ? "Bot" : "Check";
  const headerTitle = state === "partial" ? "Steps" : "Finished";

  return (
    <div className="relative py-3">
      {/* Render flat content items. Three routes:
          - tool_use items get wrapped in their own collapsible card
            (ToolCallCard) so they always carry the bordered-header
            chrome — the agent emits them flat, not inside a group
          - consecutive citations get coalesced into one Sources strip
          - everything else passes through ContentDisplay directly */}
      {flatItems.length > 0 && (
        <div className="flex flex-col gap-2">
          {groupConsecutiveCitations(flatItems).map((run) => {
            if (run.kind === "sources") {
              return (
                <div key={`sources-${run.index}`} className="px-4 py-2">
                  <SourcesStrip citations={run.citations} />
                </div>
              );
            }
            if (run.item.type === "tool_use") {
              return (
                <ToolCallCard
                  key={`tool-${run.index}`}
                  content={run.item}
                  chatId={`${chatId}-tool-${run.index}`}
                  playgroundPage={playgroundPage}
                />
              );
            }
            return (
              <ContentDisplay
                key={`flat-${run.index}`}
                content={run.item}
                chatId={`${chatId}-flat-${run.index}`}
                playgroundPage={playgroundPage}
              />
            );
          })}
        </div>
      )}

      {/* Render grouped blocks with accordion UI */}
      {toolItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{
            duration: 0.15,
            ease: "easeOut",
          }}
          className={cn(
            "relative rounded-lg bg-transparent",
            "overflow-hidden",
          )}
        >
          {isLoading && (
            <BorderTrail
              size={100}
              transition={{
                repeat: Infinity,
                duration: 10,
                ease: "linear",
              }}
            />
          )}
          {!hideHeader && (
            <div className="flex items-center justify-between p-4">
              <div className="flex items-center gap-2 align-baseline">
                {headerIcon && (
                  <span data-testid="header-icon">
                    <ForwardedIconComponent
                      name={headerIcon}
                      className={cn(
                        "h-4 w-4",
                        state !== "partial" && "text-accent-emerald-foreground",
                      )}
                      strokeWidth={1.5}
                    />
                  </span>
                )}
                <p className="m-0 flex items-center gap-2 text-sm font-semibold text-primary">
                  {headerTitle}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {!playgroundPage && (
                  <DurationDisplay duration={totalDuration} chatId={chatId} />
                )}
                <motion.div
                  animate={{ rotate: isExpanded ? 180 : 0 }}
                  transition={{ duration: 0.2, ease: "easeInOut" }}
                  onClick={() => setIsExpanded((prev) => !prev)}
                  className="cursor-pointer"
                >
                  <ChevronDown className="h-5 w-5" />
                </motion.div>
              </div>
            </div>
          )}

          {(hideHeader || isExpanded) && (
            <div className="flex flex-col gap-2">
              <Accordion
                // Auto-expand any tool that's still running so the user
                // sees the in-flight call without clicking. assistant-ui's
                // terminal variant, ai-chatbot, Claude's web UI, and
                // ChatGPT all default to expanded-while-running and
                // user-collapsible after settling. Controlled (not
                // ``defaultValue``) so tools that start running after mount
                // also auto-expand.
                type="multiple"
                value={openToolKeys}
                onValueChange={setOpenToolKeys}
                className="w-full bg-transparent flex flex-col gap-2"
              >
                {toolItems.map(
                  ({ content, toolKey, blockIndex, contentIndex }, flatIdx) => {
                    const rawTitle =
                      content.header?.title ||
                      content.name ||
                      `Tool ${flatIdx + 1}`;
                    const toolTitle =
                      typeof rawTitle === "string"
                        ? formatToolTitle(rawTitle)
                        : rawTitle;
                    const toolDuration =
                      toolElapsedTimes[toolKey] ?? content.duration ?? 0;
                    const status = getToolStatus(content);
                    const dotClass = TOOL_STATUS_CLASS[status];
                    // Drop the "Called tool" / "Node" prefix and the
                    // bg-muted code-pill chrome — consensus across
                    // assistant-ui, ai-chatbot, CopilotKit, Claude, and
                    // ChatGPT is just the tool name in medium weight as
                    // the header.

                    return (
                      <AccordionItem
                        key={toolKey}
                        value={toolKey}
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
                          <div className="text-sm text-muted-foreground px-4 pb-4 max-h-96 overflow-auto">
                            <ContentDisplay
                              playgroundPage={playgroundPage}
                              content={content}
                              chatId={`${chatId}-${blockIndex}-${contentIndex}`}
                            />
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    );
                  },
                )}
              </Accordion>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
