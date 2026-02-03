import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { ChunkInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { useGetKnowledgeBaseChunks } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { cn } from "@/utils/utils";

const CHUNKS_PER_PAGE = 10;
const TRUNCATE_LENGTH = 300;

interface ChunkCardProps {
  chunk: ChunkInfo;
  index: number;
  onCopy: (content: string) => void;
}

const ChunkCard = ({ chunk, index, onCopy }: ChunkCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const shouldTruncate = chunk.content.length > TRUNCATE_LENGTH;
  const displayContent =
    shouldTruncate && !isExpanded
      ? chunk.content.slice(0, TRUNCATE_LENGTH) + "..."
      : chunk.content;

  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border border-border bg-background p-4 transition-all duration-200",
        isExpanded && "ring-1 ring-ring",
      )}
      onClick={() => shouldTruncate && setIsExpanded(!isExpanded)}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-medium">Chunk {index}</span>
          <span className="text-sm text-muted-foreground">
            {chunk.char_count} chars
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={(e) => {
              e.stopPropagation();
              onCopy(chunk.content);
            }}
          >
            <ForwardedIconComponent
              name="Copy"
              className="h-3.5 w-3.5 text-muted-foreground"
            />
          </Button>
        </div>
        {shouldTruncate && (
          <ForwardedIconComponent
            name={isExpanded ? "ChevronUp" : "ChevronDown"}
            className="h-4 w-4 text-muted-foreground transition-transform duration-200"
          />
        )}
      </div>
      <p
        className={cn(
          "text-sm leading-relaxed text-muted-foreground transition-all duration-200",
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
  const [searchText, setSearchText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  const {
    data: chunks,
    isLoading,
    error,
  } = useGetKnowledgeBaseChunks({ kb_name: sourceId || "" });

  const handleBack = () => {
    navigate("/assets/knowledge-bases");
  };

  const handleCopyChunk = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const filteredChunks = (chunks || []).filter((chunk) =>
    chunk.content.toLowerCase().includes(searchText.toLowerCase()),
  );

  const totalPages = Math.ceil(filteredChunks.length / CHUNKS_PER_PAGE);
  const startIndex = (currentPage - 1) * CHUNKS_PER_PAGE;
  const paginatedChunks = filteredChunks.slice(
    startIndex,
    startIndex + CHUNKS_PER_PAGE,
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [searchText]);

  return (
    <div className="flex h-full w-full" data-testid="source-chunks-wrapper">
      <div className="flex h-full w-full flex-col overflow-y-auto">
        <div className="flex h-full w-full flex-col xl:container">
          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
            <div className="flex h-full flex-col justify-start">
              <div
                className="flex items-center pb-8 text-xl font-semibold"
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
                {sourceId}
              </div>

              <div className="flex h-full flex-col">
                <div className="pb-6">
                  <Input
                    icon="Search"
                    type="text"
                    placeholder="Search your documents..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    className="w-full"
                  />
                </div>

                {isLoading ? (
                  <div className="flex h-40 items-center justify-center">
                    <Loading />
                  </div>
                ) : error ? (
                  <div className="flex h-40 items-center justify-center text-muted-foreground">
                    Failed to load chunks
                  </div>
                ) : filteredChunks.length === 0 ? (
                  <div className="flex h-40 items-center justify-center text-muted-foreground">
                    No chunks found
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col gap-3">
                      {paginatedChunks.map((chunk, index) => (
                        <ChunkCard
                          key={chunk.id}
                          chunk={chunk}
                          index={startIndex + index + 1}
                          onCopy={handleCopyChunk}
                        />
                      ))}
                    </div>

                    {totalPages > 1 && (
                      <div className="flex items-center justify-between border-t border-border py-4">
                        <span className="text-sm text-muted-foreground">
                          Showing {startIndex + 1}-
                          {Math.min(
                            startIndex + CHUNKS_PER_PAGE,
                            filteredChunks.length,
                          )}{" "}
                          of {filteredChunks.length} chunks
                        </span>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setCurrentPage((p) => Math.max(1, p - 1))
                            }
                            disabled={currentPage === 1}
                          >
                            <ForwardedIconComponent
                              name="ChevronLeft"
                              className="h-4 w-4"
                            />
                            Previous
                          </Button>
                          <span className="px-2 text-sm">
                            Page {currentPage} of {totalPages}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setCurrentPage((p) => Math.min(totalPages, p + 1))
                            }
                            disabled={currentPage === totalPages}
                          >
                            Next
                            <ForwardedIconComponent
                              name="ChevronRight"
                              className="h-4 w-4"
                            />
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
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
