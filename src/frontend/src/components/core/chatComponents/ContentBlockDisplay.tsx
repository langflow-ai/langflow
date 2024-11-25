"use client";
import { BorderTrail } from "@/components/core/border-trail";
import { ContentBlock } from "@/types/chat";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "../../common/genericIconComponent";
import { Separator } from "../../ui/separator";
import ContentDisplay from "./ContentDisplay";
import DurationDisplay from "./DurationDisplay";

interface ContentBlockDisplayProps {
  contentBlocks: ContentBlock[];
  isLoading?: boolean;
  state?: string;
  chatId: string;
}

export function ContentBlockDisplay({
  contentBlocks,
  isLoading,
  state,
  chatId,
}: ContentBlockDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const totalDuration = isLoading
    ? undefined
    : contentBlocks[0]?.contents.reduce((acc, curr) => {
        return acc + (curr.duration || 0);
      }, 0);

  if (!contentBlocks?.length) {
    return null;
  }

  const lastContent =
    contentBlocks[0]?.contents[contentBlocks[0]?.contents.length - 1];
  const headerIcon =
    state === "partial" ? lastContent?.header?.icon || "Bot" : "Bot";

  const headerTitle =
    state === "partial" ? (lastContent?.header?.title ?? "Steps") : "Finished";
  // show the block title only if state === "partial"
  const showBlockTitle = state === "partial";

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
        <div
          className="flex cursor-pointer items-center justify-between p-4"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-2">
            {headerIcon && (
              <ForwardedIconComponent
                name={headerIcon}
                className="h-4 w-4"
                strokeWidth={1.5}
              />
            )}
            <div className="relative h-6 overflow-hidden">
              <motion.div
                key={headerTitle}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
              >
                <Markdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeMathjax]}
                  className="inline-block w-fit max-w-full text-[14px] font-semibold text-primary"
                >
                  {headerTitle}
                </Markdown>
              </motion.div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DurationDisplay duration={totalDuration} chatId={chatId} />
            <motion.div
              animate={{ rotate: isExpanded ? 180 : 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
            >
              <ChevronDown className="h-5 w-5" />
            </motion.div>
          </div>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded && (
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
              {contentBlocks.map((block, index) => (
                <motion.div
                  key={`${block.title}-${index}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2, delay: 0.1 }}
                  className={cn(
                    "relative",
                    index !== contentBlocks.length - 1 &&
                      "border-b border-border",
                  )}
                >
                  <AnimatePresence>
                    {showBlockTitle && (
                      <motion.div
                        initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                        animate={{
                          opacity: 1,
                          height: "auto",
                          marginBottom: 8,
                        }}
                        exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden pl-4 pt-[16px] font-medium"
                      >
                        <Markdown
                          className="text-[14px] font-semibold text-foreground"
                          remarkPlugins={[remarkGfm]}
                          linkTarget="_blank"
                          rehypePlugins={[rehypeMathjax]}
                          components={{
                            p({ node, ...props }) {
                              return (
                                <span className="inline">{props.children}</span>
                              );
                            },
                          }}
                        >
                          {block.title}
                        </Markdown>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  <div className="text-sm text-muted-foreground">
                    {block.contents.map((content, index) => (
                      <motion.div key={index}>
                        <AnimatePresence>
                          {index !== 0 && (
                            <motion.div
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.2 }}
                            >
                              <Separator orientation="horizontal" />
                            </motion.div>
                          )}
                        </AnimatePresence>
                        <ContentDisplay
                          content={content}
                          chatId={`${chatId}-${index}`}
                        />
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
