"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
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

  const toolItems = contentBlocks.flatMap((block, blockIndex) =>
    block.contents
      .filter((content) => content.type === "tool_use")
      .map((content, contentIndex) => ({
        content,
        blockIndex,
        contentIndex,
      })),
  );

  if (!toolItems.length) {
    return null;
  }

  const totalDuration = isLoading
    ? undefined
    : toolItems.reduce((acc, { content }) => acc + (content.duration || 0), 0);

  if (!contentBlocks?.length) {
    return null;
  }

  const formatTime = (ms: number) => {
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
              className="relative border-t border-border"
            >
              {toolItems.map(
                ({ content, blockIndex, contentIndex }, flatIdx) => {
                  const toolKey = `${blockIndex}-${contentIndex}`;
                  const isToolOpen = openTools[toolKey] ?? false;
                  const toolTitle =
                    content.header?.title ||
                    content.name ||
                    `Tool ${flatIdx + 1}`;
                  const toolIcon = content.header?.icon || "Hammer";
                  const toolDuration = content.duration || 0;

                  return (
                    <motion.div
                      key={toolKey}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: 0.05 }}
                      className="relative border-b border-border last:border-b-0"
                    >
                      <div
                        className="flex cursor-pointer items-center justify-between px-4 py-3"
                        onClick={() =>
                          setOpenTools((prev) => ({
                            ...prev,
                            [toolKey]: !(prev[toolKey] ?? false),
                          }))
                        }
                      >
                        <div className="flex items-center gap-2">
                          <ForwardedIconComponent
                            name={toolIcon}
                            className="h-4 w-4 text-primary"
                            strokeWidth={1.5}
                          />
                          <Markdown
                            className="text-sm font-semibold text-foreground"
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeMathjax]}
                          >
                            {toolTitle}
                          </Markdown>
                          <span className="text-xs text-emerald-500">
                            {formatTime(toolDuration)}
                          </span>
                        </div>
                        <motion.div
                          animate={{ rotate: isToolOpen ? 180 : 0 }}
                          transition={{ duration: 0.2, ease: "easeInOut" }}
                        >
                          <ChevronDown className="h-4 w-4" />
                        </motion.div>
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
