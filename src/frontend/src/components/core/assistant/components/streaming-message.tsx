import { useMemo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import LangflowLogo from "@/assets/LangflowLogoColor.svg?react";
import { cn } from "@/utils/utils";
import { parseStreamingContent } from "../helpers/streaming-parser";

type StreamingMessageProps = {
  text: string;
  isCodeExpanded: boolean;
  onToggleCode: () => void;
};

export const StreamingMessage = ({
  text,
  isCodeExpanded,
  onToggleCode,
}: StreamingMessageProps) => {
  const parsed = useMemo(() => parseStreamingContent(text), [text]);

  return (
    <div className="flex flex-col gap-2">
      {/* Pre-code text (explanation) */}
      {parsed.preCodeText && (
        <div className="flex items-start gap-2">
          <LangflowLogo className="mt-1 h-4 w-4 shrink-0" />
          <Markdown
            remarkPlugins={[remarkGfm]}
            className="markdown prose prose-sm max-w-full font-mono dark:prose-invert prose-p:my-0 prose-pre:my-0 prose-ul:my-0 prose-ol:my-0 prose-li:my-0 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_ul]:mt-0 [&_ol]:mt-0 [&_ul]:pl-4 [&_ol]:pl-4"
          >
            {parsed.preCodeText}
          </Markdown>
        </div>
      )}

      {/* Code section */}
      {parsed.code !== null && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={onToggleCode}
              className="flex items-center gap-1.5 transition-colors hover:text-foreground"
            >
              <ForwardedIconComponent
                name="ChevronRight"
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform",
                  isCodeExpanded && "rotate-90",
                )}
              />
              <span className="font-mono text-sm text-muted-foreground">
                Generating component...
              </span>
            </button>
            {!parsed.isCodeComplete && (
              <ForwardedIconComponent
                name="Loader2"
                className="h-3.5 w-3.5 animate-spin text-muted-foreground"
              />
            )}
          </div>

          {isCodeExpanded && (
            <div className="mt-1">
              <div className="relative">
                <SimplifiedCodeTabComponent language="python" code={parsed.code} />
                {!parsed.isCodeComplete && (
                  <div className="absolute bottom-2 right-2">
                    <span className="inline-block w-2 h-4 bg-primary animate-pulse" />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Cursor when no code yet */}
      {parsed.code === null && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-primary animate-pulse" />
      )}
    </div>
  );
};
