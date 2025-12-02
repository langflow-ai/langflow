import { useState, useCallback, useEffect, useMemo } from "react";
import { Search, Grid3x3, List, Filter } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import MarketplaceFlowCard from "./components/MarketplaceFlowCard";
import FlowPagination from "./components/FlowPagination";
import { useGetAllPublishedFlows } from "@/controllers/API/queries/published-flows";
import ListSkeleton from "../MainPage/components/listSkeleton";
import { debounce } from "lodash";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SortByDropdown } from "@/components/ui/SortByDropdown";
import { ViewToggle } from "@/components/ui/ViewToggle";
import { FilterIcon } from "@/assets/icons/FilterIcon";

const sortedTags = [...MARKETPLACE_TAGS].sort((a, b) =>
  a.title.localeCompare(b.title)
);

const sortOptions = [
  { label: "Name", value: "name" },
  { label: "Published Date", value: "date" },
  { label: "All Domain", value: "tags" },
];

// Storage keys for persisting filter state
const STORAGE_KEYS = {
  SEARCH: "marketplace_search_query",
  VIEW_MODE: "marketplace_view_mode",
  PAGE_INDEX: "marketplace_page_index",
  PAGE_SIZE: "marketplace_page_size",
  TAG_FILTER: "marketplace_tag_filter",
  SORT_BY: "marketplace_sort_by",
  ORDER: "marketplace_order",
};

// Helper to safely get from sessionStorage
const getStoredValue = <T,>(key: string, defaultValue: T): T => {
  try {
    const item = sessionStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
};

// Helper to safely set to sessionStorage
const setStoredValue = <T,>(key: string, value: T): void => {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error("Failed to save to sessionStorage:", key, error);
  }
};

export default function MarketplacePage() {
  // Initialize state from sessionStorage with fallback to defaults
  const [searchQuery, setSearchQuery] = useState(() =>
    getStoredValue(STORAGE_KEYS.SEARCH, "")
  );
  const [debouncedSearch, setDebouncedSearch] = useState(() =>
    getStoredValue(STORAGE_KEYS.SEARCH, "")
  );
  const [viewMode, setViewMode] = useState<"grid" | "list">(() =>
    getStoredValue(STORAGE_KEYS.VIEW_MODE, "grid")
  );
  const [pageIndex, setPageIndex] = useState(() =>
    getStoredValue(STORAGE_KEYS.PAGE_INDEX, 1)
  );
  const [pageSize, setPageSize] = useState(() =>
    getStoredValue(STORAGE_KEYS.PAGE_SIZE, 12)
  );
  const [tagFilter, setTagFilter] = useState<string | "all">(() =>
    getStoredValue(STORAGE_KEYS.TAG_FILTER, "all")
  );
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [sortBy, setSortBy] = useState<"name" | "date" | "tags">(() =>
    getStoredValue(STORAGE_KEYS.SORT_BY, "name")
  );
  const [order, setOrder] = useState<"asc" | "desc">(() =>
    getStoredValue(STORAGE_KEYS.ORDER, "asc")
  );

  // Persist searchQuery to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.SEARCH, searchQuery);
  }, [searchQuery]);

  // Persist debouncedSearch to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.SEARCH, debouncedSearch);
  }, [debouncedSearch]);

  // Persist viewMode to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.VIEW_MODE, viewMode);
  }, [viewMode]);

  // Persist pageIndex to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.PAGE_INDEX, pageIndex);
  }, [pageIndex]);

  // Persist pageSize to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.PAGE_SIZE, pageSize);
  }, [pageSize]);

  // Persist tagFilter to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.TAG_FILTER, tagFilter);
  }, [tagFilter]);

  // Persist sortBy to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.SORT_BY, sortBy);
  }, [sortBy]);

  // Persist order to sessionStorage
  useEffect(() => {
    setStoredValue(STORAGE_KEYS.ORDER, order);
  }, [order]);

  useEffect(() => {
    if (sortBy === "name") {
      setOrder("asc");
    } else if (sortBy === "date") {
      setOrder("desc");
    } else if (sortBy === "tags") {
      setOrder("asc");
    }
  }, [sortBy]);

  const debouncedSetSearchQuery = useCallback(
    debounce((value: string) => {
      setSearchQuery(value);
      // Only reset to first page when the search actually changes
      setPageIndex((prev) => (value !== searchQuery ? 1 : prev));
    }, 500),
    [searchQuery]
  );

  useEffect(() => {
    // Avoid resetting pagination on mount if the stored search equals current
    if (debouncedSearch !== searchQuery) {
      debouncedSetSearchQuery(debouncedSearch);
    }
    return () => {
      debouncedSetSearchQuery.cancel();
    };
  }, [debouncedSearch, searchQuery, debouncedSetSearchQuery]);

  const { data, isLoading } = useGetAllPublishedFlows({
    page: pageIndex,
    limit: pageSize,
    search: searchQuery || undefined,
    tags: tagFilter !== "all" ? tagFilter : undefined,
    sort_by: sortBy,
    order: order,
  });

  const items = data?.items || [];
  const total = data?.total || 0;
  const pages = data?.pages || 1;
  const currentPage = Math.min(pageIndex, pages);
  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  const visibleItems = useMemo(() => {
    const list = items || [];
    return [...list].sort((a: any, b: any) => {
      const aStatus = (a.status ?? "").toString().toUpperCase();
      const bStatus = (b.status ?? "").toString().toUpperCase();
      const isAPublished = aStatus === "PUBLISHED";
      const isBPublished = bStatus === "PUBLISHED";

      if (isAPublished && !isBPublished) return -1;
      if (!isAPublished && isBPublished) return 1;
      return 0;
    });
  }, [items]);
  const expandCards = visibleItems.length === 12;

  const handlePageChange = useCallback((newPageIndex: number) => {
    setPageIndex(newPageIndex);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPageIndex(1);
  }, []);

  // Handle filter change immediately
  const handleTagFilterChange = useCallback((value: string) => {
    setTagFilter(value);
    setPageIndex(1);
    setIsFilterOpen(false);
  }, []);

  return (
    <div className="flex h-full w-full overflow-y-auto">
      <div className="flex h-full w-full flex-col">
        <div className="flex w-full flex-1 flex-col gap-4">
          <div className="flex w-full items-center justify-between gap-4">
            <h1 className="text-menu text-xl font-medium leading-normal">
              Marketplace <span>({total} Agents)</span>
            </h1>

            <div className="flex items-center gap-3">
              <div className="relative w-[350px]">
                <Input
                  type="search"
                  icon={"Search"}
                  placeholder="Search Agents..."
                  value={debouncedSearch}
                  onChange={(e) => setDebouncedSearch(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Sort By</span>
                <SortByDropdown
                  value={sortBy}
                  onChange={(v) => setSortBy(v as typeof sortBy)}
                  options={sortOptions}
                />
              </div>

              {/* <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Sort By</span>
                <Select
                  value={sortBy}
                  onValueChange={(v) => setSortBy(v as typeof sortBy)}
                >
                  <SelectTrigger className="h-8 w-[160px] rounded-md border border-[#EBE8FF] dark:border-white/20 dark:text-white text-sm">
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent className="dark:bg-black dark:text-white">
                    <SelectItem value="name" className="dark:text-white">
                      Name
                    </SelectItem>
                    <SelectItem value="date" className="dark:text-white">
                      Published Date
                    </SelectItem>
                    <SelectItem value="tags" className="dark:text-white">
                      All Domain
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div> */}

              <Popover open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="xs"
                    className="min-w-[80px] h-8 px-2 !justify-start"
                    aria-label="Filter"
                  >
                    <FilterIcon className="!h-3 !w-3 text-secondary-font" />
                    Filter
                    {tagFilter !== "all" && (
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-menu text-[10px] text-background-surface">
                        1
                      </span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  align="end"
                  className="w-[230px] rounded-md border border-primary-border bg-background-surface p-4 shadow-[0px_0px_12px_0px_rgba(var(--boxshadow),0.12)]"
                >
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-primary-font">
                        Domain
                      </div>
                      <Select
                        value={tagFilter}
                        onValueChange={handleTagFilterChange}
                      >
                        <SelectTrigger className="h-8 w-full rounded-md border border-primary-border text-sm">
                          <SelectValue placeholder="All Domain" />
                        </SelectTrigger>
                        <SelectContent className="w-[230px] max-h-64 overflow-y-auto">
                          <SelectItem value="all">All Domain</SelectItem>
                          {sortedTags.map((tag) => (
                            <SelectItem key={tag.id} value={tag.id}>
                              {tag.title}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex gap-4 items-center justify-between pt-2">
                      <Button
                        variant="outline"
                        size="md"
                        className="w-full"
                        onClick={() => {
                          setIsFilterOpen(false);
                        }}
                      >
                        Cancel
                      </Button>
                      {/* <Button
                        size="md"
                        className="w-full"
                        onClick={() => {
                          setTagFilter(pendingTag);
                          setPageIndex(1);
                          setIsFilterOpen(false);
                        }}
                      >
                        Apply
                      </Button> */}
                    </div>
                  </div>
                </PopoverContent>
              </Popover>

              <ViewToggle value={viewMode} onChange={setViewMode} />

              {/* <div className="flex items-center gap-1 rounded-md border border-[#EBE8FF] dark:border-white/20 p-1">
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
              </div> */}
            </div>
          </div>

          {isLoading ? (
            <div
              className={
                viewMode === "grid"
                  ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 max-h-[calc(100vh-212px)] overflow-y-auto "
                  : "flex flex-col gap-4 flex-1 min-h-[calc(100vh-280px)]"
              }
            >
              <ListSkeleton />
              <ListSkeleton />
              <ListSkeleton />
            </div>
          ) : (
            <>
              {items.length > 0 && (
                <div
                  className={`max-h-[calc(100vh-172px)] overflow-auto
                    ${viewMode === "grid"
                      ? "grid grid-cols-2 md:grid-cols-3 3xl:grid-cols-4 gap-4 "
                      : "flex flex-col gap-2 flex-1"
                    }`}
                >
                  {visibleItems.map((item: any) => (
                    <MarketplaceFlowCard
                      key={item.id}
                      item={item}
                      viewMode={viewMode}
                      expand={viewMode === "grid" && expandCards}
                    />
                  ))}
                </div>
              )}

              {items.length === 0 && (
                <div className="flex h-full items-center justify-center text-[24px] font-medium text-secondary-font opacity-40">
                  {searchQuery
                    ? "No marketplace flows match your search."
                    : "No marketplace flows available yet."}
                </div>
              )}
            </>
          )}

          {!isLoading && total > 0 && (
            <div className="flex justify-between gap-4 mt-auto">
              {!isLoading && total > 0 && (
                <div className="flex items-center justify-end text-sm text-primary-font font-medium">
                  {`Showing ${start + 1} - ${Math.min(
                    end,
                    total
                  )} results of ${total}`}
                </div>
              )}

              <FlowPagination
                currentPage={currentPage}
                pageSize={pageSize}
                totalPages={pages}
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
