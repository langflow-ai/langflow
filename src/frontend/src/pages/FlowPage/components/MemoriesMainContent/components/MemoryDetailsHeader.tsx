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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { cn } from "@/utils/utils";
import { ALL_SESSIONS_VALUE } from "../hooks/useMemorySessionResolver";
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
      setSuccessData({
        title: t("memory.refreshedSuccess", { name: memory.name }),
      });
    } catch (error) {
      setErrorData({
        title: t("memory.refreshedError"),
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

  const isAllSessions =
    !selectedSession || selectedSession === ALL_SESSIONS_VALUE;
  const sessionLabel = isAllSessions
    ? t("memory.allSessions")
    : selectedSession;

  return (
    <div className="flex items-end justify-between border-b border-border bg-background px-6 py-4">
      <div className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">{memory.name}</h2>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex cursor-default items-center gap-2">
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
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p>{t("memory.autoCaptureTooltip")}</p>
              <a
                href="https://docs.langflow.org/memory-bases"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 flex items-center gap-1 text-xs text-primary underline"
              >
                {t("memory.readTheDocs")}
                <IconComponent name="ExternalLink" className="h-3 w-3" />
              </a>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
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
                  <DropdownMenuItem
                    className="flex items-center justify-between"
                    onSelect={() => setSelectedSession(ALL_SESSIONS_VALUE)}
                  >
                    <span className="truncate">{t("memory.allSessions")}</span>
                    <IconComponent
                      name="Check"
                      className={
                        isAllSessions
                          ? "h-4 w-4 text-primary"
                          : "h-4 w-4 opacity-0"
                      }
                    />
                  </DropdownMenuItem>
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
                        {t("memory.loadingSessions")}
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
          description={t("memory.deleteDescription", { name: memory.name })}
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
            <IconComponent name="Trash2" className="h-4 w-4 text-destructive" />
          </Button>
        </DeleteConfirmationModal>
      </div>
    </div>
  );
}
