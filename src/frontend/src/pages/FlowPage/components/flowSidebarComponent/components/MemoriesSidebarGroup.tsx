import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import type { MemoryInfo } from "@/controllers/API/queries/memories/use-get-memories";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import CreateMemoryModal from "@/modals/createMemoryModal";

interface MemoriesSidebarGroupProps {
  selectedMemoryId: string | null;
  onSelectMemory: (id: string | null) => void;
}

const MemoriesEmptyState = ({
  onCreateClick,
}: {
  onCreateClick: () => void;
}) => {
  return (
    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center px-4 py-8 text-center">
      <IconComponent
        name="Brain"
        className="mb-3 h-10 w-10 text-muted-foreground opacity-50"
      />
      <p className="text-sm text-muted-foreground">No memories yet</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Create a memory to give your flow long-term context
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-3"
        onClick={onCreateClick}
      >
        <IconComponent name="Plus" className="mr-1 h-4 w-4" />
        New Memory
      </Button>
    </div>
  );
};

const MemoriesLoadingState = () => {
  return (
    <div className="flex h-full min-h-[100px] w-full items-center justify-center">
      <IconComponent name="Loader2" className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
};

const getStatusStyles = (status: MemoryInfo["status"]) => {
  switch (status) {
    case "idle":
      return "bg-muted text-muted-foreground";
    case "generating":
      return "bg-warning-background text-warning";
    case "updating":
      return "bg-primary/10 text-primary";
    case "failed":
      return "bg-destructive/10 text-destructive";
    default:
      return "bg-muted text-muted-foreground";
  }
};

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return "";
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  } catch {
    return "";
  }
};

const MemoryListItem = ({
  memory,
  isSelected,
  onSelect,
}: {
  memory: MemoryInfo;
  isSelected: boolean;
  onSelect: () => void;
}) => {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1 rounded-md px-2 py-2 text-left transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50 text-foreground",
      )}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 truncate">
          {memory.is_active && (
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" title="Auto-capture active" />
          )}
          <span className="truncate text-xs font-medium">{memory.name}</span>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-1.5 py-0.5 text-[10px]",
            getStatusStyles(memory.status),
          )}
        >
          {memory.status}
        </span>
      </div>
      <div className="flex w-full items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {memory.total_chunks}{" "}chunks{" "}&middot;{" "}{memory.sessions_count}{" "}sessions
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {formatTimestamp(memory.created_at)}
        </span>
      </div>
      {(memory.status === "generating" || memory.status === "updating") && (
        <div className="flex w-full items-center gap-2">
          <div className="h-1 flex-1 rounded-full bg-muted">
            <div className="h-1 animate-pulse rounded-full bg-primary" style={{ width: "60%" }} />
          </div>
          <span className="text-[10px] text-muted-foreground">
            {memory.total_messages_processed} msgs
          </span>
        </div>
      )}
    </button>
  );
};

const MemoriesSidebarGroup = ({
  selectedMemoryId,
  onSelectMemory,
}: MemoriesSidebarGroupProps) => {
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const [createModalOpen, setCreateModalOpen] = useState(false);

  const { data: memories, isLoading } = useGetMemories(
    { flowId: currentFlowId ?? undefined },
    { enabled: !!currentFlowId, refetchInterval: 5000 },
  );

  const sortedMemories = useMemo(() => {
    if (!memories) return [];
    return [...memories].sort(
      (a, b) =>
        new Date(b.created_at || 0).getTime() -
        new Date(a.created_at || 0).getTime(),
    );
  }, [memories]);

  useEffect(() => {
    if (sortedMemories.length === 0) {
      // No memories left — clear selection
      if (selectedMemoryId !== null) {
        onSelectMemory(null);
      }
      return;
    }
    // Auto-select first if nothing selected, or if selected memory was deleted
    if (
      selectedMemoryId === null ||
      !sortedMemories.some((m) => m.id === selectedMemoryId)
    ) {
      onSelectMemory(sortedMemories[0].id);
    }
  }, [sortedMemories, selectedMemoryId, onSelectMemory]);

  const handleClose = useCallback(() => {
    setActiveSection("components");
    if (!open) {
      toggleSidebar();
    }
  }, [setActiveSection, open, toggleSidebar]);

  const handleCreateSuccess = useCallback(
    (memoryId: string) => {
      onSelectMemory(memoryId);
    },
    [onSelectMemory],
  );

  const hasMemories = sortedMemories.length > 0;

  return (
    <>
      <SidebarGroup className={`p-3 pr-2${!hasMemories ? " h-full" : ""}`}>
        <SidebarGroupLabel className="flex w-full cursor-default items-center justify-between">
          <span>Memories</span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCreateModalOpen(true)}
              className="h-6 w-6"
              data-testid="new-memory-btn"
            >
              <IconComponent name="Plus" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClose}
              className="h-6 w-6"
              data-testid="close-memories-sidebar"
            >
              <IconComponent name="X" className="h-4 w-4" />
            </Button>
          </div>
        </SidebarGroupLabel>
        <SidebarGroupContent className="h-full overflow-y-auto">
          {isLoading && <MemoriesLoadingState />}
          {!isLoading && !hasMemories && (
            <MemoriesEmptyState onCreateClick={() => setCreateModalOpen(true)} />
          )}
          {!isLoading && hasMemories && (
            <SidebarMenu>
              {sortedMemories.map((memory) => (
                <SidebarMenuItem key={memory.id}>
                  <MemoryListItem
                    memory={memory}
                    isSelected={selectedMemoryId === memory.id}
                    onSelect={() => onSelectMemory(memory.id)}
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          )}
        </SidebarGroupContent>
      </SidebarGroup>

      {currentFlow && (
        <CreateMemoryModal
          open={createModalOpen}
          setOpen={setCreateModalOpen}
          flowId={currentFlow.id}
          flowName={currentFlow.name}
          onSuccess={handleCreateSuccess}
        />
      )}
    </>
  );
};

export default MemoriesSidebarGroup;
