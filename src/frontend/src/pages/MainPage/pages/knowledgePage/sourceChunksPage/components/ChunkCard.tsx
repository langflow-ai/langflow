import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChunkInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { cn } from "@/utils/utils";

interface ChunkCardProps {
  chunk: ChunkInfo;
  index: number;
  onCopy: (content: string) => void;
}

const ChunkCard = ({ chunk, index, onCopy }: ChunkCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const contentRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const el = contentRef.current;
    if (el) {
      setIsOverflowing(el.scrollHeight > el.clientHeight);
    }
  }, [chunk.content]);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCopy(chunk.content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "rounded-lg border border-muted bg-muted p-3 transition-all duration-200",
        isOverflowing && "cursor-pointer",
      )}
      onClick={() => isOverflowing && setIsExpanded(!isExpanded)}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">Chunk {index}</span>
          <Badge
            variant="secondary"
            size="sq"
            className="text-xs text-muted-foreground"
          >
            {chunk.char_count} chars
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "group h-6 w-6 transition-colors",
              isCopied && "text-accent-emerald-foreground",
            )}
            onClick={handleCopy}
          >
            <ForwardedIconComponent
              name={isCopied ? "Check" : "Copy"}
              className={cn(
                "h-3.5 w-3.5 transition-colors",
                isCopied
                  ? "text-accent-emerald-foreground"
                  : "text-muted-foreground group-hover:text-foreground",
              )}
            />
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-4">
            {isOverflowing && (
              <ForwardedIconComponent
                name={isExpanded ? "ChevronUp" : "ChevronDown"}
                className="h-4 w-4 text-muted-foreground transition-transform duration-200"
              />
            )}
          </div>
        </div>
      </div>
      <p
        ref={contentRef}
        className={cn(
          "text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap break-words",
          !isExpanded && "line-clamp-2",
        )}
      >
        {chunk.content}
      </p>
    </div>
  );
};

export default ChunkCard;
