import { useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  ChunkInfo,
  useGetKnowledgeBaseChunks,
} from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { cn } from "@/utils/utils";
import { CHUNKS_PER_PAGE, TRUNCATE_LENGTH } from "./constants";

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

export const SourceChunksPage = () => {
  const { sourceId } = useParams<{ sourceId: string }>();
  const navigate = useCustomNavigate();
  const [currentPage, setCurrentPage] = useState(1);

  const {
    data: paginatedResponse,
    isLoading,
    error,
  } = useGetKnowledgeBaseChunks({
    kb_name: sourceId || "",
    page: currentPage,
    limit: CHUNKS_PER_PAGE,
  });

  const handleBack = () => {
    navigate("/assets/knowledge-bases");
  };

  const handleCopyChunk = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const chunks = paginatedResponse?.chunks || [];
  const totalPages = paginatedResponse?.total_pages || 0;
  const total = paginatedResponse?.total || 0;
  const startIndex = ((paginatedResponse?.page || 1) - 1) * CHUNKS_PER_PAGE;

  return (
    <div className="flex h-full w-full" data-testid="source-chunks-wrapper">
      <div className="flex h-full w-full flex-col overflow-hidden">
        <div className="flex h-full w-full flex-col overflow-hidden xl:container">
          <div className="flex h-full flex-col px-5 pt-10">
            <div className="flex h-full flex-col overflow-hidden">
              <div
                className="flex shrink-0 items-center pb-4 text-base h-[44px] font-semibold"
                data-testid="mainpage_title"
              >
                <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                  <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                    <SidebarTrigger>
                      <ForwardedIconComponent
                        name="PanelLeftOpen"
                        aria-hidden="true"
                      />
                    </SidebarTrigger>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleBack}
                  className="mr-2 h-8 w-8"
                >
                  <ForwardedIconComponent
                    name="ArrowLeft"
                    className="h-4 w-4"
                  />
                </Button>
                <span style={{ textTransform: "none" }}>{sourceId}</span>
              </div>

              <div className="flex flex-1 flex-col overflow-hidden">
                {isLoading ? (
                  <div className="flex h-40 items-center justify-center">
                    <Loading />
                  </div>
                ) : error ? (
                  <div className="flex h-40 items-center justify-center text-muted-foreground">
                    Failed to load chunks
                  </div>
                ) : chunks.length === 0 ? (
                  <div className="flex h-40 items-center justify-center text-muted-foreground">
                    No chunks found
                  </div>
                ) : (
                  <div className="flex flex-1 flex-col overflow-hidden">
                    <div className="flex-1 overflow-y-auto">
                      <div className="flex flex-col gap-3">
                        {chunks.map((chunk, index) => (
                          <ChunkCard
                            key={chunk.id}
                            chunk={chunk}
                            index={startIndex + index + 1}
                            onCopy={handleCopyChunk}
                          />
                        ))}
                      </div>
                    </div>

                    {totalPages > 1 && (
                      <div className="shrink-0 pb-4 pt-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">
                            Showing {startIndex + 1}-
                            {Math.min(startIndex + CHUNKS_PER_PAGE, total)} of{" "}
                            {total} chunks
                          </span>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => setCurrentPage(1)}
                              disabled={currentPage === 1}
                            >
                              <ForwardedIconComponent
                                name="ChevronsLeft"
                                className="h-4 w-4"
                              />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() =>
                                setCurrentPage((p) => Math.max(1, p - 1))
                              }
                              disabled={currentPage === 1}
                            >
                              <ForwardedIconComponent
                                name="ChevronLeft"
                                className="h-4 w-4"
                              />
                            </Button>
                            <div className="flex items-center gap-1.5 px-2 text-sm">
                              <span>Page</span>
                              <input
                                type="number"
                                min={1}
                                max={totalPages}
                                value={currentPage}
                                onChange={(e) => {
                                  const value = parseInt(e.target.value, 10);
                                  if (!isNaN(value)) {
                                    setCurrentPage(
                                      Math.max(1, Math.min(totalPages, value)),
                                    );
                                  }
                                }}
                                className="h-7 w-16 rounded border border-input bg-background px-2 text-center text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                              />
                              <span>of {totalPages}</span>
                            </div>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() =>
                                setCurrentPage((p) =>
                                  Math.min(totalPages, p + 1),
                                )
                              }
                              disabled={currentPage === totalPages}
                            >
                              <ForwardedIconComponent
                                name="ChevronRight"
                                className="h-4 w-4"
                              />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => setCurrentPage(totalPages)}
                              disabled={currentPage === totalPages}
                            >
                              <ForwardedIconComponent
                                name="ChevronsRight"
                                className="h-4 w-4"
                              />
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SourceChunksPage;
