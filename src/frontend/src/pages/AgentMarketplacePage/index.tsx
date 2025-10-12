import { useState, useCallback } from "react";
import { Search, Grid3x3, List, Filter, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useFolderStore } from "@/stores/foldersStore";
import PaginatorComponent from "@/components/common/paginatorComponent";
import AgentCard from "./components/AgentCard";
import ListSkeleton from "../MainPage/components/listSkeleton";

export default function AgentMarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const { data: folderData, isLoading } = useGetFolderQuery({
    id: myCollectionId!,
    page: pageIndex,
    size: pageSize,
    is_flow: true,
    is_component: false,
    search: searchQuery,
  });

  const agents = folderData?.flows?.items ?? [];
  const filteredAgents = agents;

  const paginationData = {
    page: folderData?.flows?.page ?? 1,
    size: folderData?.flows?.size ?? 12,
    total: folderData?.flows?.total ?? 0,
    pages: folderData?.flows?.pages ?? 0,
  };

  const handlePageChange = useCallback((newPageIndex: number, newPageSize: number) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
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
                  placeholder="Search agent..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
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
                {filteredAgents.map((flow) => (
                  <AgentCard key={flow.id} flow={flow} />
                ))}
              </div>

              {/* Empty State */}
              {filteredAgents.length === 0 && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  No agents found matching your search.
                </div>
              )}
            </>
          )}

          {/* Pagination */}
          {!isLoading && paginationData.total > 0 && (
            <div className="mt-6 flex justify-end border-t pt-4">
              <PaginatorComponent
                pageIndex={paginationData.page}
                pageSize={paginationData.size}
                rowsCount={[12, 24, 48, 96]}
                totalRowsCount={paginationData.total}
                paginate={handlePageChange}
                pages={paginationData.pages}
                isComponent={false}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
