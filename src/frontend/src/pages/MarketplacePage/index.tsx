import { useState, useCallback, useEffect } from "react";
import { Search, Grid3x3, List } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import MarketplaceFlowCard from "./components/MarketplaceFlowCard";
import { useGetAllPublishedFlows } from "@/controllers/API/queries/published-flows";
import ListSkeleton from "../MainPage/components/listSkeleton";
import { debounce } from "lodash";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";

export default function MarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize] = useState(12);
  const [category, setCategory] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"published_at" | "name">(
    "published_at"
  );
  const [order] = useState<"asc" | "desc">("desc");

  // Debounce search
  const debouncedSetSearchQuery = useCallback(
    debounce((value: string) => {
      setSearchQuery(value);
      setPageIndex(1);
    }, 500),
    []
  );

  useEffect(() => {
    debouncedSetSearchQuery(debouncedSearch);
    return () => {
      debouncedSetSearchQuery.cancel();
    };
  }, [debouncedSearch, debouncedSetSearchQuery]);

  // Fetch published flows
  const { data, isLoading } = useGetAllPublishedFlows({
    page: pageIndex,
    limit: pageSize,
    search: searchQuery || undefined,
    category: category !== "all" ? category : undefined,
    sort_by: sortBy,
    order: order,
  });

  const items = data?.items || [];
  const total = data?.total || 0;
  const pages = data?.pages || 1;

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-[#FBFAFF] dark:bg-black dark:text-white">
      <div className="flex h-full w-full flex-col">
        <div className="flex w-full flex-1 flex-col gap-4 p-4 md:p-6">
          {/* Header */}
          <div className="flex w-full items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <h1 className="text-[#350E84] dark:text-white text-[21px] font-medium">
                Agent Marketplace
              </h1>
              <span className="text-[#350E84] dark:text-white text-[21px] font-medium">
                ({total} Agents)
              </span>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="relative w-[400px]">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search agents..."
                  value={debouncedSearch}
                  onChange={(e) => setDebouncedSearch(e.target.value)}
                  className="pl-10 h-9 rounded-md border border-[#EBE8FF] dark:border-white/20 dark:bg-black dark:text-white placeholder:text-muted-foreground dark:placeholder:text-white/60"
                />
              </div>

              {/* Category Filter */}
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent className="dark:bg-black dark:text-white">
                  <SelectItem value="all" className="dark:text-white">
                    All Categories
                  </SelectItem>
                  {MARKETPLACE_TAGS.map((tag) => (
                    <SelectItem key={tag} value={tag} className="dark:text-white">
                      {tag}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Sort */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Sort By</span>
                <Select
                  value={sortBy}
                  onValueChange={(v) => setSortBy(v as typeof sortBy)}
                >
                  <SelectTrigger className="w-[160px] h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="dark:bg-black dark:text-white">
                    <SelectItem
                      value="published_at"
                      className="dark:text-white"
                    >
                      Recently Published
                    </SelectItem>
                    <SelectItem value="name" className="dark:text-white">
                      Name
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* View Toggle */}
              <div className="flex items-center gap-1 rounded-md border border-[#EBE8FF] dark:border-white/20 p-1">
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
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              <ListSkeleton />
              <ListSkeleton />
              <ListSkeleton />
            </div>
          ) : (
            <>
              {/* Flow Grid */}
              <div
                className={
                  viewMode === "grid"
                    ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
                    : "flex flex-col gap-4"
                }
              >
                {items.map((item: any) => (
                  <MarketplaceFlowCard
                    key={item.id}
                    item={item}
                    viewMode={viewMode}
                  />
                ))}
              </div>

              {/* Empty State */}
              {items.length === 0 && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  No published flows found.
                </div>
              )}

              {/* Pagination */}
              {total > 0 && (
                <div className="mt-6 flex justify-between items-center border-t dark:border-white/20 pt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {(pageIndex - 1) * pageSize + 1} -{" "}
                    {Math.min(pageIndex * pageSize, total)} of {total}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={pageIndex === 1}
                      onClick={() => setPageIndex(pageIndex - 1)}
                    >
                      Previous
                    </Button>
                    <span className="flex items-center px-3 text-sm">
                      Page {pageIndex} of {pages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={pageIndex === pages}
                      onClick={() => setPageIndex(pageIndex + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
