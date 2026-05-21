import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { cn } from "@/utils/utils";
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
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
      setSuccessData({ title: `Memory "${memory.name}" refreshed` });
    } catch (error) {
      setErrorData({
        title: "Failed to refresh memory",
        list: extractApiErrorMessages(error),
      });
    } finally {
      setIsRefreshing(false);
    }
  };

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

  const sessionLabel = selectedSession ?? "All Sessions";

  return (
    <div className="flex items-end justify-between border-b border-border bg-background px-6 py-4">
      <div className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">{memory.name}</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {t("memory.activate")}
          </span>
          <Switch
            checked={memory.is_active}
            onCheckedChange={(checked) => handleToggleActive(checked)}
            aria-label={t("memory.toggleAutoCapture")}
            className="data-[state=checked]:bg-accent-emerald-foreground"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        {sessions && sessions.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t("memory.sessionLabel")}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  aria-label={t("memory.sessionFilter")}
                  className="w-[180px] justify-between rounded-[10px] px-3"
                >
                  <span className="truncate">
                    {sessionLabel.length > 20
                      ? `${sessionLabel.slice(0, 20)}...`
                      : sessionLabel}
                  </span>
                  <IconComponent
                    name="ChevronDown"
                    className="ml-2 h-4 w-4 shrink-0 text-muted-foreground"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-[180px] p-0">
                <div
                  className="max-h-[240px] overflow-y-auto py-1"
                  onScroll={handleSessionsScroll}
                >
                  {sessions.map((sid) => {
                    const isSelected = sid === selectedSession;
                    return (
                      <DropdownMenuItem
                        key={sid}
                        className="flex items-center justify-between"
                        onSelect={() => setSelectedSession(sid)}
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
          </div>
        )}

        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={isRefreshing}
          aria-label={t("memory.reloadSessions")}
        >
          <IconComponent
            name="RefreshCw"
            className={cn("h-4 w-4", isRefreshing && "animate-spin")}
          />
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
            variant="ghost"
            size="icon"
            disabled={deleteMutation.isPending}
            aria-label="Delete memory"
          >
            <IconComponent
              name="Trash2"
              className="h-4 w-4 text-destructive"
            />
          </Button>
        </DeleteConfirmationModal>
      </div>
    </div>
  );
}
