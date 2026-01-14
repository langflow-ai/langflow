"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import { BorderTrail } from "@/components/core/border-trail";
import { useToolDurations } from "@/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-tool-durations";
import type { ContentBlock } from "@/types/chat";
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

interface ContentBlockDisplayProps {
  contentBlocks: ContentBlock[];
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

  // Use shared hook for tool duration tracking
  const { toolElapsedTimes, toolItems } = useToolDurations(
    contentBlocks,
    isLoading ?? false,
  );

  if (!toolItems.length) {
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

  const formatTime = (ms: number, showMsOnly: boolean = false) => {
    if (showMsOnly) {
      return `${Math.round(ms)}ms`;
    }
    if (ms < 1000) return `${Math.round(ms)}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  const headerIcon = state === "partial" ? "Bot" : "Check";
  const headerTitle = state === "partial" ? "Steps" : "Finished";
  // No block title in flattened tool list
  const showBlockTitle = false;

  return (
    <div className="relative py-3">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.2,
          ease: "easeOut",
        }}
        className={cn("relative rounded-lg bg-transparent", "overflow-hidden")}
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
              type="multiple"
              className="w-full bg-transparent flex flex-col gap-2"
            >
              {toolItems.map(
                ({ content, toolKey, blockIndex, contentIndex }, flatIdx) => {
                  const rawTitle =
                    content.header?.title ||
                    content.name ||
                    `Tool ${flatIdx + 1}`;
                  // Remove "Executed" from the title, replace underscores with spaces, and convert to uppercase
                  const toolTitle =
                    typeof rawTitle === "string"
                      ? rawTitle
                          .replace(/^Executed\s+/i, "")
                          .replace(/_/g, " ")
                          .replace(/\*\*/g, "")
                          .trim()
                          .toUpperCase()
                      : rawTitle;
                  // Use elapsed time if tool is active, otherwise use duration
                  const toolDuration =
                    toolElapsedTimes[toolKey] ?? content.duration ?? 0;

                  return (
                    <AccordionItem
                      key={toolKey}
                      value={toolKey}
                      className="border border-border rounded-lg overflow-hidden bg-background"
                    >
                      <AccordionTrigger className="hover:bg-muted hover:no-underline px-1 py-1.5">
                        <div className="flex items-center justify-between w-full pr-2">
                          <div className="flex items-center gap-1 text-sm font-normal min-w-0 flex-1 overflow-hidden">
                            <div className="text-muted-foreground whitespace-nowrap flex-shrink-0">
                              Called tool{" "}
                            </div>
                            <div className="truncate flex-1 muted-foreground bg-muted py-1 px-1.5 rounded-sm text-xs max-w-fit">
                              <p className="truncate font-normal font-mono">
                                {toolTitle}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-emerald-500">
                              {formatTime(toolDuration, true)}
                            </span>
                          </div>
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
    </div>
  );
}
