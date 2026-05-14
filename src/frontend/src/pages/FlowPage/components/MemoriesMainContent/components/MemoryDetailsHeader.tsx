import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import type { MemoryDetailsHeaderProps } from "../types";

export function MemoryDetailsHeader({
  memory,
  sessions,
  selectedSession,
  setSelectedSession,
  deleteMutation,
  handleToggleActive,
  onRefresh,
  fetchNextSessionsPage,
  hasNextSessionsPage,
  isFetchingNextSessionsPage,
}: MemoryDetailsHeaderProps) {
  const effectiveSession = (selectedSession ?? sessions?.[0] ?? "") as
    | string
    | null;

  const handleSessionsScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    if (
      el.scrollHeight - el.scrollTop <= el.clientHeight * 2 &&
      hasNextSessionsPage &&
      !isFetchingNextSessionsPage
    ) {
      fetchNextSessionsPage();
    }
  };

  return (
    <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
      <div className="flex items-center gap-3">
        <IconComponent
          name="BrainCog"
          className="h-5 w-5 text-muted-foreground"
        />
        <div>
          <h2 className="text-sm font-semibold">{memory.name}</h2>
          {memory.description && (
            <p className="text-xs text-muted-foreground">
              {memory.description}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          aria-label="Reload sessions and messages"
        >
          <IconComponent name="RefreshCw" className="h-4 w-4" />
        </Button>

        {sessions && sessions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                aria-label="Session filter"
                disabled={sessions.length <= 1 && !hasNextSessionsPage}
                className="w-[240px] justify-between px-3"
              >
                <span className="truncate">
                  {effectiveSession && effectiveSession.length > 20
                    ? `${effectiveSession.slice(0, 20)}...`
                    : (effectiveSession ?? "")}
                </span>
                <IconComponent
                  name="ChevronDown"
                  className="ml-2 h-4 w-4 shrink-0 text-muted-foreground"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[240px] p-0">
              <div
                className="max-h-[240px] overflow-y-auto py-1"
                onScroll={handleSessionsScroll}
              >
                {sessions.map((sid) => {
                  const isSelected = sid === effectiveSession;
                  return (
                    <DropdownMenuItem
                      key={sid}
                      className="flex items-center justify-between"
                      onSelect={(e) => {
                        e.preventDefault();
                        setSelectedSession(sid);
                      }}
                    >
                      <span className="truncate">{sid}</span>
                      <IconComponent
                        name="Check"
                        className={
                          isSelected
                            ? "h-4 w-4 text-primary"
                            : "h-4 w-4 opacity-0"
                        }
                      />
                    </DropdownMenuItem>
                  );
                })}
                {isFetchingNextSessionsPage && (
                  <div className="py-1 text-center">
                    <span className="text-xs text-muted-foreground">
                      Loading…
                    </span>
                  </div>
                )}
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => handleToggleActive((prevIsActive) => !prevIsActive)}
          aria-pressed={memory.is_active}
          aria-label={
            memory.is_active ? "Disable auto-capture" : "Enable auto-capture"
          }
          className="gap-2"
        >
          <IconComponent
            name={memory.is_active ? "ToggleRight" : "ToggleLeft"}
            className={
              memory.is_active
                ? "h-4 w-4 text-emerald-600 dark:text-emerald-400"
                : "h-4 w-4 text-muted-foreground"
            }
          />
          <span>Auto-capture</span>
          <span
            data-testid="memory-auto-capture-state"
            className={
              memory.is_active
                ? "rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
                : "rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400"
            }
          >
            {memory.is_active ? "ON" : "OFF"}
          </span>
        </Button>

        <DeleteConfirmationModal
          description={`memory "${memory.name}"`}
          onConfirm={(e) => {
            e.stopPropagation();
            deleteMutation.mutate({ memoryId: memory.id });
          }}
          asChild
        >
          <Button
            variant="outline"
            size="sm"
            disabled={deleteMutation.isPending}
          >
            <IconComponent name="Trash2" className="h-4 w-4" />
            Delete
          </Button>
        </DeleteConfirmationModal>
      </div>
    </div>
  );
}
