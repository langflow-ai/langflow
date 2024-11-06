"use client";
import { BorderTrail } from "@/components/core/border-trail";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { ContentBlock } from "@/types/chat";
import { cn } from "@/utils/utils";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "../genericIconComponent";
import ContentDisplay from "./ContentDisplay";

interface ContentBlockDisplayProps {
  contentBlocks: ContentBlock[];
  isLoading?: boolean;
  state?: string;
}

export function ContentBlockDisplay({
  contentBlocks,
  isLoading,
  state,
}: ContentBlockDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!contentBlocks?.length) {
    return null;
  }

  const lastContent =
    contentBlocks[0]?.contents[contentBlocks[0]?.contents.length - 1];
  const headerIcon =
    state === "partial" ? lastContent?.header?.icon || "Bot" : "Bot";
  const headerTitle =
    state === "partial"
      ? lastContent?.header?.title ||
        `Steps (${contentBlocks[0]?.contents.length})`
      : "Steps";

  const renderContent = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "relative rounded-lg border border-border bg-background",
        "overflow-hidden",
      )}
    >
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
          <Markdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeMathjax]}
            className="inline-block w-fit max-w-full font-semibold text-primary"
          >
            {headerTitle}
          </Markdown>
        </div>
        <ChevronDown
          className={cn(
            "h-5 w-5 transition-transform",
            isExpanded ? "rotate-180" : "",
          )}
        />
      </div>

      {isExpanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="relative border-t border-border"
        >
          {contentBlocks.map((block, index) => (
            <div
              key={`${block.title}-${index}`}
              className={cn(
                "relative p-4",
                index !== contentBlocks.length - 1 && "border-b border-border",
              )}
            >
              <div className="mb-2 font-medium">
                <Markdown
                  remarkPlugins={[remarkGfm]}
                  linkTarget="_blank"
                  rehypePlugins={[rehypeMathjax]}
                  components={{
                    p({ node, ...props }) {
                      return <span className="inline">{props.children}</span>;
                    },
                  }}
                >
                  {block.title}
                </Markdown>
              </div>
              <div className="text-sm text-muted-foreground">
                {block.contents.map((content, index) => (
                  <ContentDisplay key={index} content={content} />
                ))}
              </div>
            </div>
          ))}
        </motion.div>
      )}
    </motion.div>
  );

  return (
    <div className="relative py-3">
      {renderContent()}
      {isLoading && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative mt-4 rounded-lg border border-border bg-background p-4"
        >
          <BorderTrail
            className="bg-zinc-600 opacity-50 dark:bg-zinc-400"
            size={60}
            transition={{
              repeat: Infinity,
              duration: 3,
              ease: "linear",
            }}
          />
          <div className="relative z-10 flex flex-col space-y-3">
            <TextShimmer className="w-25">Processing...</TextShimmer>
            <div className="flex animate-pulse flex-col space-y-2">
              <div className="h-2 w-1/4 rounded bg-muted"></div>
              <div className="h-2 w-1/2 rounded bg-muted"></div>
              <div className="h-2 w-1/3 rounded bg-muted"></div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
