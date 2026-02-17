import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useGetKnowledgeBaseChunks } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import ChunkCard from "./components/ChunkCard";
import { CHUNKS_PER_PAGE } from "./constants";

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

  const filteredChunks = (chunks || [])
    .map((chunk, originalIndex) => ({
      ...chunk,
      originalIndex: originalIndex + 1,
    }))
    .filter((chunk) =>
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
                <div className="shrink-0 pb-4 xl:w-[600px]">
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
                  <div className="flex flex-1 flex-col overflow-hidden">
                    <div className="flex-1 overflow-y-auto">
                      <div className="flex flex-col gap-3">
                        {paginatedChunks.map((chunk) => (
                          <ChunkCard
                            key={chunk.id}
                            chunk={chunk}
                            index={chunk.originalIndex}
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
                            {Math.min(
                              startIndex + CHUNKS_PER_PAGE,
                              filteredChunks.length,
                            )}{" "}
                            of {filteredChunks.length} chunks
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
