import { useState, useCallback, useEffect, useMemo } from "react";
import { debounce } from "lodash";
import { Search, Grid3x3, List, Filter, Moon, Sun } from "lucide-react";
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

import MarketplaceAgentCard from "./components/MarketplaceAgentCard";
import AgentPagination from "./components/AgentPagination";
import ListSkeleton from "../MainPage/components/listSkeleton";
import { useGetAgentMarketplaceQuery } from "@/controllers/API/queries/agent-marketplace/use-get-agent-marketplace";
import { STATIC_MARKETPLACE_AGENTS } from "./data/agentsList";
import type { AgentSpecItem } from "@/controllers/API/queries/agent-marketplace/use-get-agent-marketplace";
import useTheme from "@/customization/hooks/use-custom-theme";

export default function AgentMarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [selectedCategory, setSelectedCategory] = useState<
    string | undefined
  >();
  const [sortBy, setSortBy] = useState<"name" | "status">("name");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [tagFilter, setTagFilter] = useState<string | "all">("all");
  const [pendingTag, setPendingTag] = useState<string | "all">("all");

  // Debounce the search query
  const debouncedSetSearchQuery = useCallback(
    debounce((value: string) => {
      setSearchQuery(value);
      setPageIndex(1); // Reset to first page when searching
    }, 1000),
    []
  );

  useEffect(() => {
    debouncedSetSearchQuery(debouncedSearch);

    return () => {
      debouncedSetSearchQuery.cancel(); // Cleanup on unmount
    };
  }, [debouncedSearch, debouncedSetSearchQuery]);

  const { data: marketplaceData, isLoading } = useGetAgentMarketplaceQuery(
    {},
    {
      refetchOnWindowFocus: false,
    }
  );

  // Build a set of normalized names from the static agents list
  const staticNameSet = useMemo(() => {
    const set = new Set<string>();
    STATIC_MARKETPLACE_AGENTS.forEach((item) => {
      const name = (item.spec?.name ?? item.file_name)?.trim().toLowerCase();
      if (name) set.add(name);
    });
    return set;
  }, []);

  // Use only API agents whose names exist in the static list
  const apiItems = useMemo(() => {
    const list = marketplaceData?.items ?? [];
    return list.filter((item) => {
      const name = (item.spec?.name ?? item.file_name)?.trim().toLowerCase();
      return !!name && staticNameSet.has(name);
    });
  }, [marketplaceData, staticNameSet]);
  const apiNameSet = useMemo(() => {
    const set = new Set<string>();
    apiItems.forEach((item) => {
      const name = (item.spec?.name ?? item.file_name)?.trim().toLowerCase();
      if (name) set.add(name);
    });
    return set;
  }, [apiItems]);

  const staticFiltered = useMemo(() => {
    return STATIC_MARKETPLACE_AGENTS.filter((item) => {
      const name = (item.spec?.name ?? item.file_name)?.trim().toLowerCase();
      return !!name && !apiNameSet.has(name);
    });
  }, [apiNameSet]);

  // Build a lookup from normalized name -> static tags from agentsList
  const staticTagsByName = useMemo(() => {
    const map = new Map<string, string[]>();
    STATIC_MARKETPLACE_AGENTS.forEach((sa) => {
      const name = (sa.spec?.name ?? sa.file_name)?.trim().toLowerCase();
      const tags = Array.isArray(sa.spec?.tags) ? sa.spec?.tags ?? [] : [];
      if (name && tags.length > 0) {
        map.set(name, tags);
      }
    });
    return map;
  }, []);

  // Normalize tags and override API tags with static tags when available
  const normalizeItemTags = useCallback(
    (item: AgentSpecItem): AgentSpecItem => {
      const normalizedName = (item.spec?.name ?? item.file_name)
        ?.trim()
        .toLowerCase();

      const staticTags = normalizedName
        ? staticTagsByName.get(normalizedName)
        : undefined;

      const currentTags = Array.isArray(item.spec?.tags)
        ? item.spec?.tags ?? []
        : typeof (item as any).spec?.tag === "string"
        ? [String((item as any).spec?.tag)]
        : [];

      const tagsToUse =
        staticTags && staticTags.length > 0 ? staticTags : currentTags;

      if (item.spec) {
        return { ...item, spec: { ...item.spec, tags: tagsToUse } };
      }
      return { ...item, spec: { tags: tagsToUse } } as AgentSpecItem;
    },
    [staticTagsByName]
  );

  const items = useMemo(() => {
    const combined = [...apiItems, ...staticFiltered];
    return combined.map(normalizeItemTags);
  }, [apiItems, staticFiltered, normalizeItemTags]);

  const allTags = useMemo(() => {
    // Deduplicate case-insensitively while preserving display casing
    const byLower = new Map<string, string>();
    items.forEach((item) => {
      const tags = Array.isArray(item.spec?.tags) ? item.spec?.tags : [];
      tags.forEach((t) => {
        const key = t.toLowerCase();
        if (!byLower.has(key)) byLower.set(key, t);
      });
    });
    return Array.from(byLower.values()).sort((a, b) => a.localeCompare(b));
  }, [items]);

  useEffect(() => {
    if (isFilterOpen) {
      setPendingTag(tagFilter);
    }
  }, [isFilterOpen, tagFilter]);

  const normalizedSearch = searchQuery.trim().toLowerCase();
  const filteredItemsBySearch = normalizedSearch
    ? items.filter((item) => {
        const name = (item.spec?.name ?? item.file_name)?.toLowerCase();
        const tags = Array.isArray(item.spec?.tags)
          ? item.spec?.tags.map((t) => t.toLowerCase())
          : typeof (item as any).spec?.tag === "string"
          ? [String((item as any).spec?.tag).toLowerCase()]
          : [];
        return (
          (name && name.includes(normalizedSearch)) ||
          tags.some((t) => t.includes(normalizedSearch))
        );
      })
    : items;

  const filteredItems =
    tagFilter !== "all" && tagFilter.trim() !== ""
      ? filteredItemsBySearch.filter((item) => {
          const tags = Array.isArray(item.spec?.tags)
            ? item.spec?.tags
            : typeof (item as any).spec?.tag === "string"
            ? [String((item as any).spec?.tag)]
            : [];
          return tags.some((t) => t.toLowerCase() === tagFilter.toLowerCase());
        })
      : filteredItemsBySearch;

  const sortedItems = [...filteredItems].sort((a, b) => {
    if (sortBy === "name") {
      const an = (a.spec?.name ?? a.file_name).toLowerCase();
      const bn = (b.spec?.name ?? b.file_name).toLowerCase();
      return an.localeCompare(bn);
    }
    const as = (a.spec?.status ?? "").toString().toLowerCase();
    const bs = (b.spec?.status ?? "").toString().toLowerCase();
    return as.localeCompare(bs);
  });

  const total = sortedItems.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(pageIndex, pages);
  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  const visibleItems = sortedItems.slice(start, end);
  // Cards should only expand when exactly 12 agents are shown on the page
  const expandCards = visibleItems.length === 12;

  const handlePageChange = useCallback((newPageIndex: number) => {
    setPageIndex(newPageIndex);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPageIndex(1); // Reset to first page when changing page size
  }, []);

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto dark:bg-black dark:text-white">
      <div className="flex h-full w-full flex-col">
        <div className="flex w-full flex-1 flex-col gap-4 p-4 md:p-6">
          {/* Header + Controls Row */}
          <div className="flex w-full items-center justify-between gap-4">
            {/* Left: Title + Search */}
            <div className="flex items-center gap-4">
              <h1 className="text-primary dark:text-white text-[21px] font-medium leading-normal not-italic">
                Marketplace
              </h1>
              <span className="text-primary dark:text-white text-[21px] font-medium leading-normal not-italic">
                ({total} Agents)
              </span>
            </div>

            {/* Right: Sort + Filter + View Toggle */}
            <div className="flex items-center gap-3">
              {/* Search Input */}
              <div className="relative w-[500px] max-w-[500px]">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search agents..."
                  value={debouncedSearch}
                  onChange={(e) => setDebouncedSearch(e.target.value)}
                  className="h-9 rounded-md border border-[#EBE8FF] dark:border-white/20 dark:bg-black dark:text-white placeholder:text-muted-foreground dark:placeholder:text-white/60"
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
                    <SelectItem value="status" className="dark:text-white">
                      Status
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Filter Button + Popover */}
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
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  align="end"
                  className="w-[360px] rounded-md border border-[#EBE8FF] dark:border-white/20 bg-white dark:bg-black dark:text-white p-4 shadow-md"
                >
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="text-base font-semibold">Tags</div>
                      <Select
                        value={pendingTag}
                        onValueChange={(v) => setPendingTag(v as string)}
                      >
                        <SelectTrigger className="h-10 w-full rounded-md border border-[#EBE8FF] dark:border-white/20 text-sm dark:text-white">
                          <SelectValue placeholder="All Tags" />
                        </SelectTrigger>
                        <SelectContent className="max-h-64 overflow-y-auto dark:bg-black dark:text-white">
                          <SelectItem value="all" className="dark:text-white">
                            All Tags
                          </SelectItem>
                          {allTags.map((t) => (
                            <SelectItem
                              key={t}
                              value={t}
                              className="dark:text-white"
                            >
                              {t}
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
                        className="h-9 rounded-md bg-primary text-white hover:bg-[#2D0B6E]"
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
            <div
              className={
                viewMode === "grid"
                  ? "grid auto-rows-fr grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 flex-1 min-h-[calc(100vh-280px)]"
                  : "flex flex-col gap-4 flex-1 min-h-[calc(100vh-280px)]"
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
                    ? `grid ${
                        expandCards ? "auto-rows-fr" : "auto-rows-auto"
                      } grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 flex-1 min-h-[calc(100vh-280px)]`
                    : "flex flex-col gap-4 flex-1 min-h-[calc(100vh-280px)]"
                }
              >
                {visibleItems.map((item) => (
                  <MarketplaceAgentCard
                    key={`${item.folder_name}/${item.file_name}`}
                    item={item}
                    viewMode={viewMode}
                    expand={viewMode === "grid" && expandCards}
                  />
                ))}
              </div>

              {/* Empty State */}
              {sortedItems.length === 0 && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  {searchQuery
                    ? "No marketplace agents match your search."
                    : "No marketplace agents available yet."}
                </div>
              )}

              {/* Results Counter */}
              {!isLoading && total > 0 && (
                <div className="mt-2 flex items-center justify-end text-xs text-[#444444] dark:text-white/60">
                  {`Showing ${start + 1} - ${Math.min(
                    end,
                    total
                  )} results of ${total}`}
                </div>
              )}
            </>
          )}

          {/* Pagination */}
          {!isLoading && total > 0 && (
            <div className="mt-6 flex justify-end border-t dark:border-white/20 pt-4">
              <AgentPagination
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
