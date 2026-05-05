import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import { statusBgColors, statusColors } from "../helpers";
import { MemoriesSidebarProps } from "../types";

export function MemoriesSidebar({
  memories,
  filteredMemories,
  memoriesSearch,
  setMemoriesSearch,
  selectedMemoryId,
  currentFlowId,
  onSelectMemory,
  onCreateMemory,
}: MemoriesSidebarProps) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-background">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <IconComponent
              name="Brain"
              className="h-4 w-4 text-muted-foreground"
            />
            <h2 className="text-sm font-semibold">Memories</h2>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={onCreateMemory}
            disabled={!currentFlowId}
          >
            <IconComponent name="Plus" className="mr-1.5 h-3.5 w-3.5" />
            Create
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {(() => {
            const count = memories?.length ?? 0;
            return `${count} ${count === 1 ? "memory" : "memories"}`;
          })()}
        </p>
      </div>

      <div className="p-4">
        <Input
          value={memoriesSearch}
          onChange={(e) => setMemoriesSearch(e.target.value)}
          placeholder="Search memories..."
        />
      </div>

      <div className="flex-1 overflow-auto px-2 pb-4">
        {!filteredMemories.length ? (
          <div className="px-3 py-6 text-center">
            <IconComponent
              name="Brain"
              className="mx-auto mb-2 h-8 w-8 text-muted-foreground opacity-50"
            />
            <p className="text-xs text-muted-foreground">
              {memoriesSearch.trim() ? "No memories found" : "No memories yet"}
            </p>
            {!memoriesSearch.trim() && (
              <Button
                className="mt-3"
                size="sm"
                variant="outline"
                onClick={onCreateMemory}
                disabled={!currentFlowId}
              >
                <IconComponent name="Plus" className="mr-1.5 h-3.5 w-3.5" />
                Create Memory
              </Button>
            )}
          </div>
        ) : (
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
                      {memoryItem.is_active && (
                        <span
                          className="h-2 w-2 shrink-0 rounded-full bg-accent-emerald-foreground"
                          aria-label="enabled"
                          title="enabled"
                        />
                      )}
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
                  <span
                    className={cn(
                      "ml-2 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
                      statusBgColors[memoryItem.status] || "bg-muted",
                      statusColors[memoryItem.status] ||
                        "text-muted-foreground",
                    )}
                  >
                    {memoryItem.status}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
