import { useState, useCallback, useEffect } from "react";
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

const sortedTags = [...MARKETPLACE_TAGS].sort((a, b) => 
  a.title.localeCompare(b.title)
);

// Storage keys for persisting filter state
const STORAGE_KEYS = {
  SEARCH: 'marketplace_search_query',
  VIEW_MODE: 'marketplace_view_mode',
  PAGE_INDEX: 'marketplace_page_index',
  PAGE_SIZE: 'marketplace_page_size',
  TAG_FILTER: 'marketplace_tag_filter',
  SORT_BY: 'marketplace_sort_by',
  ORDER: 'marketplace_order',
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
    console.error('Failed to save to sessionStorage:', key, error);
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
  const [pendingTag, setPendingTag] = useState<string | "all">(() => 
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

  useEffect(() => {
    if (isFilterOpen) {
      setPendingTag(tagFilter);
    }
  }, [isFilterOpen, tagFilter]);

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
  const visibleItems = items;
  const expandCards = visibleItems.length === 12;

  const handlePageChange = useCallback((newPageIndex: number) => {
    setPageIndex(newPageIndex);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPageIndex(1);
  }, []);

  return (
    <div className="flex h-full w-full overflow-y-auto dark:bg-black dark:text-white">
      <div className="flex h-full w-full flex-col">
        <div className="flex w-full flex-1 flex-col gap-4">
          <div className="flex w-full items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <h1 className="text-[#350E84] dark:text-white text-[21px] font-medium leading-normal not-italic">
                Marketplace
              </h1>
              <span className="text-[#350E84] dark:text-white text-[21px] font-medium leading-normal not-italic">
                ({total} Agents)
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="relative w-[500px] max-w-[500px]">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search Agents..."
                  value={debouncedSearch}
                  onChange={(e) => setDebouncedSearch(e.target.value)}
                  className="h-9 rounded-md border border-[#EBE8FF] dark:border-white/20 dark:bg-black dark:text-white placeholder:text-muted-foreground dark:placeholder:text-white/60 focus:border-1 focus:border-primary"
                />
              </div>

              <div className="flex items-center gap-2">
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
              </div>

              <Popover open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 gap-2 rounded-md border border-[#EBE8FF] dark:border-white/20"
                    aria-label="Filter"
                  >
                    <Filter className="h-4 w-4 text-muted-foreground" />
                    Filter
                    {tagFilter !== "all" && (
                      <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] text-white">
                        1
                      </span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  align="end"
                  className="w-[360px] rounded-md border border-[#EBE8FF] dark:border-white/20 bg-white dark:bg-black dark:text-white p-4 shadow-md"
                >
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="text-base font-semibold">Domain</div>
                      <Select
                        value={pendingTag}
                        onValueChange={(v) => setPendingTag(v as string)}
                      >
                        <SelectTrigger className="h-10 w-full rounded-md border border-[#EBE8FF] dark:border-white/20 text-sm dark:text-white">
                          <SelectValue placeholder="All Domain" />
                        </SelectTrigger>
                        <SelectContent className="max-h-64 overflow-y-auto dark:bg-black dark:text-white">
                          <SelectItem value="all" className="dark:text-white">
                            All Domain
                          </SelectItem>
                          {sortedTags.map((tag) => (
                            <SelectItem
                              key={tag.id}
                              value={tag.id}
                              className="dark:text-white"
                            >
                              {tag.title}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-9 rounded-md border border-[#EBE8FF] dark:border-white/20"
                        onClick={() => {
                          setPendingTag(tagFilter);
                          setIsFilterOpen(false);
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        className="h-9 rounded-md bg-[#350E84] text-white hover:bg-[#2D0B6E]"
                        onClick={() => {
                          setTagFilter(pendingTag);
                          setPageIndex(1);
                          setIsFilterOpen(false);
                        }}
                      >
                        Apply
                      </Button>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>

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
                  className={
                    viewMode === "grid"
                      ? `grid ${
                          expandCards ? "" : "auto-rows-auto"
                        } grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 max-h-[calc(100vh-212px)] overflow-y-auto place-items-start`
                      : "flex flex-col gap-4 flex-1 min-h-[calc(100vh-280px)]"
                  }
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
                <div className="flex h-full items-center justify-center text-[24px] font-medium text-muted-foreground/60">
                  {searchQuery
                    ? "No marketplace flows match your search."
                    : "No marketplace flows available yet."}
                </div>
              )}
            </>
          )}

          {!isLoading && total > 0 && (
            <div className="flex justify-between gap-4 pt-4 mt-auto">
              {!isLoading && total > 0 && (
                <div className="flex items-center justify-end text-xs text-[#444444] dark:text-white/60">
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