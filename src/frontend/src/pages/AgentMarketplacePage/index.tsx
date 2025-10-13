import { useState, useCallback, useEffect } from "react";
import { debounce } from "lodash";
import { Search, Grid3x3, List, Filter, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

import AgentCard from "./components/AgentCard";
import AgentPagination from "./components/AgentPagination";
import ListSkeleton from "../MainPage/components/listSkeleton";
import useGetPublishedAgentsQuery from "@/controllers/API/queries/published-agent/use-get-publshed-agent";

export default function AgentMarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>();

  // Debounce the search query
  const debouncedSetSearchQuery = useCallback(
    debounce((value: string) => {
      setSearchQuery(value);
      setPageIndex(1); // Reset to first page when searching
    }, 1000),
    [],
  );

  useEffect(() => {
    debouncedSetSearchQuery(debouncedSearch);

    return () => {
      debouncedSetSearchQuery.cancel(); // Cleanup on unmount
    };
  }, [debouncedSearch, debouncedSetSearchQuery]);

  const { data: publishedAgentsData, isLoading } = useGetPublishedAgentsQuery({
    page: pageIndex,
    size: pageSize,
    category_id: selectedCategory,
    is_published: true,
    include_deleted: false,
  });

  const agents = publishedAgentsData?.items ?? [];
  

  const filteredAgents = searchQuery 
    ? agents.filter(agent => 
        agent.display_name && 
        agent.display_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : agents;

  const paginationData = {
    page: publishedAgentsData?.page ?? 1,
    size: publishedAgentsData?.size ?? 12,
    total: publishedAgentsData?.total ?? 0,
    pages: publishedAgentsData?.pages ?? 0,
  };

  const handlePageChange = useCallback((newPageIndex: number) => {
    setPageIndex(newPageIndex);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPageIndex(1); // Reset to first page when changing page size
  }, []);

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-gray-50 dark:bg-background">
      <div className="flex h-full w-full flex-col 3xl:container">
        <div className="flex flex-1 flex-col p-6">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-foreground mb-6">
              Agent Marketplace
            </h1>

            {/* Search and Controls */}
            <div className="flex items-center gap-3">
              {/* Search Input */}
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search agents..."
                  value={debouncedSearch}
                  onChange={(e) => setDebouncedSearch(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* Sort By */}
              <Button variant="outline" className="gap-2">
                <span className="text-sm">Sort By</span>
                <ChevronDown className="h-4 w-4" />
              </Button>

              {/* Filter */}
              <Button variant="outline" className="gap-2">
                <Filter className="h-4 w-4" />
                <span className="text-sm">Filter</span>
              </Button>

              {/* View Toggle */}
              <div className="flex items-center gap-1 rounded-md border p-1">
                <Button
                  variant={viewMode === "list" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("list")}
                  className="h-8 w-8 p-0"
                >
                  <List className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("grid")}
                  className="h-8 w-8 p-0"
                >
                  <Grid3x3 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {isLoading ? (
            <div
              className={
                viewMode === "grid"
                  ? "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
                  : "flex flex-col gap-4"
              }
            >
              <ListSkeleton />
              <ListSkeleton />
              <ListSkeleton />
            </div>
          ) : (
            <>
              {/* Agent Grid */}
              <div
                className={
                  viewMode === "grid"
                    ? "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
                    : "flex flex-col gap-4"
                }
              >
                {filteredAgents.map((agent) => (
                  <AgentCard key={agent.id} agent={agent} />
                ))}
              </div>

              {/* Empty State */}
              {filteredAgents.length === 0 && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  {searchQuery 
                    ? "No agents found matching your search."
                    : "No published agents available yet."
                  }
                </div>
              )}
            </>
          )}

          {/* Pagination */}
          {!isLoading && paginationData.total > 0 && (
            <div className="mt-6 flex justify-end border-t pt-4">
              <AgentPagination
                currentPage={paginationData.page}
                pageSize={paginationData.size}
                totalPages={paginationData.pages}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}