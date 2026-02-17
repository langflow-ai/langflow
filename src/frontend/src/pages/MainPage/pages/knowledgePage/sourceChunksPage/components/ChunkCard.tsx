import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChunkInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { cn } from "@/utils/utils";
import { TRUNCATE_LENGTH } from "../constants";

interface ChunkCardProps {
  chunk: ChunkInfo;
  index: number;
  onCopy: (content: string) => void;
}

const ChunkCard = ({ chunk, index, onCopy }: ChunkCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const shouldTruncate = chunk.content.length > TRUNCATE_LENGTH;
  const displayContent =
    shouldTruncate && !isExpanded
      ? chunk.content.slice(0, TRUNCATE_LENGTH) + "..."
      : chunk.content;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCopy(chunk.content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border border-muted bg-muted p-3 transition-all duration-200",
      )}
      onClick={() => shouldTruncate && setIsExpanded(!isExpanded)}
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
          {/* TODO: Add score when semantic search is implemented
          <Badge
            variant="secondary"
            size="sq"
            className="text-xs text-muted-foreground"
          >
            {chunk?.score ?? "N/A"} score
          </Badge>
          */}
          <div className="w-4">
            {shouldTruncate && (
              <ForwardedIconComponent
                name={isExpanded ? "ChevronUp" : "ChevronDown"}
                className="h-4 w-4 text-muted-foreground transition-transform duration-200"
              />
            )}
          </div>
        </div>
      </div>
      <p
        className={cn(
          "text-sm leading-relaxed text-muted-foreground transition-all duration-200 whitespace-pre-wrap break-words",
          !isExpanded && shouldTruncate && "line-clamp-4",
        )}
      >
        {displayContent}
      </p>
    </div>
  );
};

export default ChunkCard;
