import type { UIEvent } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import { SIDEBAR_SCROLL_THRESHOLD_PX } from "../MemoriesMainContent.constants";
import { MemoriesSidebarProps } from "../types";

export function MemoriesSidebar({
  filteredMemories,
  memoriesSearch,
  setMemoriesSearch,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
  selectedMemoryId,
  currentFlowId,
  onSelectMemory,
  onCreateMemory,
}: MemoriesSidebarProps) {
  const { t } = useTranslation();
  const handleScroll = (e: UIEvent<HTMLDivElement>) => {
    if (!fetchNextPage || !hasNextPage || isFetchingNextPage) return;
    const el = e.currentTarget;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining < SIDEBAR_SCROLL_THRESHOLD_PX) {
      fetchNextPage();
    }
  };

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-background">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <IconComponent
            name="BrainCog"
            className="h-4 w-4 text-muted-foreground"
          />
          <h2 className="text-sm font-semibold">{t("memory.sidebarTitle")}</h2>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onCreateMemory}
          disabled={!currentFlowId}
          className="mt-3 rounded-[10px]"
        >
          <IconComponent name="Plus" className="h-3.5 w-3.5" />
          {t("memory.createButton")}
        </Button>
      </div>

      <div className="p-4">
        <Input
          value={memoriesSearch}
          onChange={(e) => setMemoriesSearch(e.target.value)}
          placeholder={t("memory.searchMemories")}
        />
      </div>

      <div className="flex-1 overflow-auto px-2 pb-4" onScroll={handleScroll}>
        {!filteredMemories.length && memoriesSearch.trim() && (
          <div className="px-3 py-6 text-center">
            <IconComponent
              name="BrainCog"
              className="mx-auto mb-2 h-8 w-8 text-muted-foreground opacity-50"
            />
            <p className="text-xs text-muted-foreground">
              {t("memory.noMemoriesFound")}
            </p>
          </div>
        )}
        {filteredMemories.length > 0 && (
          <div className="flex flex-col gap-1">
            {filteredMemories.map((memoryItem) => {
              const isSelected = selectedMemoryId === memoryItem.id;
              return (
                <button
                  key={memoryItem.id}
                  type="button"
                  onClick={() => onSelectMemory?.(memoryItem.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors",
                    isSelected
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-accent/50",
                  )}
                >
                  <div className="min-w-0">
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full",
                          memoryItem.is_active
                            ? "bg-accent-emerald-foreground"
                            : "bg-muted-foreground",
                        )}
                        role="img"
                        aria-label={
                          memoryItem.is_active
                            ? t("memory.autoCaptureEnabled")
                            : t("memory.autoCaptureDisabled")
                        }
                        title={
                          memoryItem.is_active
                            ? t("memory.autoCaptureEnabled")
                            : t("memory.autoCaptureDisabled")
                        }
                      />
                      <div className="truncate text-sm font-medium">
                        {memoryItem.name}
                      </div>
                    </div>
                    {memoryItem.description && (
                      <div className="truncate text-xs text-muted-foreground">
                        {memoryItem.description}
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
