"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import { BorderTrail } from "@/components/core/border-trail";
import type { ContentBlock } from "@/types/chat";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import { Separator } from "../../ui/separator";
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
  const [openTools, setOpenTools] = useState<Record<string, boolean>>({});
  const [toolStartTimes, setToolStartTimes] = useState<Record<string, number>>(
    {},
  );
  const [elapsedTimes, setElapsedTimes] = useState<Record<string, number>>({});

  const toolItems = contentBlocks.flatMap((block, blockIndex) =>
    block.contents
      .filter((content) => content.type === "tool_use")
      .map((content, contentIndex) => ({
        content,
        blockIndex,
        contentIndex,
      })),
  );

  // Track tool start times and update elapsed times in real-time
  useEffect(() => {
    const newStartTimes: Record<string, number> = {};
    const newElapsedTimes: Record<string, number> = {};

    toolItems.forEach(({ content, blockIndex, contentIndex }) => {
      const toolKey = `${blockIndex}-${contentIndex}`;
      const toolDuration = content.duration || 0;

      // If tool has no duration and is loading, track its start time
      if (isLoading && toolDuration === 0) {
        if (!toolStartTimes[toolKey]) {
          // Tool just started
          newStartTimes[toolKey] = Date.now();
        } else {
          // Tool already started, calculate elapsed time
          newElapsedTimes[toolKey] = Date.now() - toolStartTimes[toolKey];
        }
      } else if (toolDuration > 0) {
        // Tool has finished, use its duration
        newElapsedTimes[toolKey] = toolDuration;
      }
    });

    if (Object.keys(newStartTimes).length > 0) {
      setToolStartTimes((prev) => ({ ...prev, ...newStartTimes }));
    }
  }, [toolItems, isLoading, toolStartTimes]);

  // Update elapsed times in real-time for active tools
  useEffect(() => {
    if (!isLoading) return;

    const interval = setInterval(() => {
      setElapsedTimes((prev) => {
        const updated: Record<string, number> = { ...prev };
        let hasChanges = false;

        toolItems.forEach(({ content, blockIndex, contentIndex }) => {
          const toolKey = `${blockIndex}-${contentIndex}`;
          const toolDuration = content.duration || 0;

          // Only update if tool is active (no duration yet)
          if (toolDuration === 0 && toolStartTimes[toolKey]) {
            const elapsed = Date.now() - toolStartTimes[toolKey];
            if (updated[toolKey] !== elapsed) {
              updated[toolKey] = elapsed;
              hasChanges = true;
            }
          }
        });

        return hasChanges ? updated : prev;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isLoading, toolItems, toolStartTimes]);

  if (!toolItems.length) {
    return null;
  }

  const totalDuration = isLoading
    ? undefined
    : toolItems.reduce((acc, { content, blockIndex, contentIndex }) => {
        const toolKey = `${blockIndex}-${contentIndex}`;
        const toolDuration = elapsedTimes[toolKey] ?? content.duration ?? 0;
        return acc + toolDuration;
      }, 0);

  if (!contentBlocks?.length) {
    return null;
  }

  const formatTime = (ms: number) => {
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
        className={cn(
          "relative rounded-lg border border-border bg-background",
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

        <AnimatePresence initial={false}>
          {(hideHeader || isExpanded) && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{
                height: "auto",
                opacity: 1,
                transition: {
                  height: { duration: 0.2 },
                  opacity: { duration: 0.1, delay: 0.1 },
                },
              }}
              exit={{
                height: 0,
                opacity: 0,
                transition: {
                  height: { duration: 0.2 },
                  opacity: { duration: 0.1 },
                },
              }}
              className="relative"
            >
              {toolItems.map(
                ({ content, blockIndex, contentIndex }, flatIdx) => {
                  const toolKey = `${blockIndex}-${contentIndex}`;
                  const isToolOpen = openTools[toolKey] ?? false;
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
                    elapsedTimes[toolKey] ?? content.duration ?? 0;

                  return (
                    <motion.div
                      key={toolKey}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: 0.05 }}
                      className="relative "
                    >
                      <div
                        className="flex cursor-pointer items-center justify-between px-1 py-1.5 rounded-sm muted text-muted-foreground w-full"
                        onClick={() =>
                          setOpenTools((prev) => ({
                            ...prev,
                            [toolKey]: !(prev[toolKey] ?? false),
                          }))
                        }
                      >
                        <div className="flex items-center gap-1 text-sm font-normal min-w-0 flex-1 overflow-hidden">
                          <motion.div
                            animate={{ rotate: isToolOpen ? 90 : 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="flex-shrink-0"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </motion.div>
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
                            {formatTime(toolDuration)}
                          </span>
                        </div>
                      </div>
                      <AnimatePresence>
                        {isToolOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{
                              height: "auto",
                              opacity: 1,
                              transition: {
                                height: { duration: 0.2 },
                                opacity: { duration: 0.1, delay: 0.1 },
                              },
                            }}
                            exit={{
                              height: 0,
                              opacity: 0,
                              transition: {
                                height: { duration: 0.2 },
                                opacity: { duration: 0.1 },
                              },
                            }}
                            className="text-sm text-muted-foreground px-4 pb-4 max-h-96 overflow-auto"
                          >
                            <ContentDisplay
                              playgroundPage={playgroundPage}
                              content={content}
                              chatId={`${chatId}-${blockIndex}-${contentIndex}`}
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  );
                },
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
