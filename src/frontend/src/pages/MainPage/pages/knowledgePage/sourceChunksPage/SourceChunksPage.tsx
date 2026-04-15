import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useGetKnowledgeBaseChunks } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import ChunkCard from "./components/ChunkCard";
import { CHUNKS_PER_PAGE, PAGE_SIZE_OPTIONS } from "./constants";

export const SourceChunksPage = () => {
  const { sourceId } = useParams<{ sourceId: string }>();
  const navigate = useCustomNavigate();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [pageSize, setPageSize] = useState<number>(CHUNKS_PER_PAGE);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(value);
      setCurrentPage(1);
    }, 300);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  const {
    data: paginatedResponse,
    isLoading,
    error,
  } = useGetKnowledgeBaseChunks({
    kb_name: sourceId || "",
    page: currentPage,
    limit: pageSize,
    search: debouncedSearch || undefined,
  });

  const handleBack = () => {
    navigate("/assets/knowledge-bases");
  };

  const handleCopyChunk = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setCurrentPage(1);
    setPageInput("1");
  };

  const handlePageInputChange = (value: string) => {
    setPageInput(value);
  };

  const commitPageInput = () => {
    const value = parseInt(pageInput, 10);
    if (!isNaN(value) && value >= 1 && value <= totalPages) {
      setCurrentPage(value);
      setPageInput(String(value));
    } else {
      setPageInput(String(currentPage));
    }
  };

  const handlePageInputBlur = () => {
    commitPageInput();
  };

  const handlePageInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      commitPageInput();
      e.currentTarget.blur();
    }
  };

  const chunks = paginatedResponse?.chunks || [];
  const totalPages = paginatedResponse?.total_pages || 0;
  const total = paginatedResponse?.total || 0;
  const startIndex = ((paginatedResponse?.page || 1) - 1) * pageSize;

  return (
    <div
      className="flex h-full w-full flex-col"
      data-testid="source-chunks-wrapper"
    >
      <div className="flex h-full w-full flex-col overflow-hidden pt-10 px-5">
        <div
          className="flex shrink-0 items-center pb-4 text-base h-[44px] font-semibold"
          data-testid="mainpage_title"
        >
          <div className="xl:container flex items-center">
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
              <ForwardedIconComponent name="ArrowLeft" className="h-4 w-4" />
            </Button>
            <span style={{ textTransform: "none" }}>{sourceId}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center pb-4">
          <div className="xl:container">
            <div className="relative w-full xl:w-5/12">
              <ForwardedIconComponent
                name="Search"
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                placeholder="Search chunks..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                data-testid="chunks-search-input"
              />
            </div>
          </div>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          {isLoading ? (
            <div className="flex flex-1 w-full flex-col items-center justify-center gap-3">
              <Loading size={36} />
              <span className="text-sm text-muted-foreground pt-3">
                Loading Chunks...
              </span>
            </div>
          ) : error ? (
            <div className="flex flex-1 items-center justify-center text-muted-foreground">
              Failed to load chunks
            </div>
          ) : chunks.length === 0 ? (
            <div className="flex flex-1 items-center justify-center text-muted-foreground">
              No chunks found
            </div>
          ) : (
            <div className="flex flex-1 flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto">
                <div className="xl:container">
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
              </div>

              {totalPages > 1 && (
                <div className="shrink-0 pb-4 pt-3">
                  <div className="xl:container">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground whitespace-nowrap">
                            Per page:
                          </span>
                          <Select
                            value={String(pageSize)}
                            onValueChange={(val) =>
                              handlePageSizeChange(Number(val))
                            }
                          >
                            <SelectTrigger
                              className="h-8 w-[70px] text-sm"
                              data-testid="chunks-page-size-select"
                            >
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="min-w-[70px]">
                              {PAGE_SIZE_OPTIONS.map((opt) => (
                                <SelectItem key={opt} value={String(opt)}>
                                  {opt}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          Showing {startIndex + 1}-
                          {Math.min(startIndex + pageSize, total)} of {total}{" "}
                          chunks
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => {
                            setCurrentPage(1);
                            setPageInput("1");
                          }}
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
                          onClick={() => {
                            const newPage = Math.max(1, currentPage - 1);
                            setCurrentPage(newPage);
                            setPageInput(String(newPage));
                          }}
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
                            value={pageInput}
                            onChange={(e) =>
                              handlePageInputChange(e.target.value)
                            }
                            onBlur={handlePageInputBlur}
                            onKeyDown={handlePageInputKeyDown}
                            className="h-7 w-16 rounded border border-input bg-background px-2 text-center text-sm focus:outline-none focus:ring-1 focus:ring-ring [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-inner-spin-button]:opacity-100 [&::-webkit-inner-spin-button]:[filter:invert(1)] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-outer-spin-button]:opacity-100 [&::-webkit-outer-spin-button]:[filter:invert(1)]"
                          />
                          <span>of {totalPages}</span>
                        </div>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => {
                            const newPage = Math.min(
                              totalPages,
                              currentPage + 1,
                            );
                            setCurrentPage(newPage);
                            setPageInput(String(newPage));
                          }}
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
                          onClick={() => {
                            setCurrentPage(totalPages);
                            setPageInput(String(totalPages));
                          }}
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
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SourceChunksPage;
