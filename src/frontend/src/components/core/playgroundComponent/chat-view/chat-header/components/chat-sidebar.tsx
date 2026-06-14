import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { useGetFlowId } from "../../../hooks/use-get-flow-id";
import { SessionSelector } from "./session-selector";

interface ChatSidebarProps {
  sessions: string[];
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  onDeleteSession?: (sessionId: string) => void;
  onOpenLogs?: (sessionId: string) => void;
  onRenameSession?: (oldId: string, newId: string) => Promise<void>;
  onBulkDeleteSessions?: (sessionIds: string[], onSuccess: () => void) => void;
}

export function ChatSidebar({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  onDeleteSession,
  onOpenLogs,
  onRenameSession,
  onBulkDeleteSessions,
}: ChatSidebarProps) {
  const { t } = useTranslation();
  const [openMenuSession, setOpenMenuSession] = useState<string | null>(null);
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(
    new Set(),
  );
  const currentFlowId = useGetFlowId();
  const isShareablePlayground = useFlowStore((state) => state.playgroundPage);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  // Filter out the default session (currentFlowId) from selectable sessions
  const selectableSessions = useMemo(
    () => sessions.filter((session) => session !== currentFlowId),
    [sessions, currentFlowId],
  );

  const visibleSession = currentSessionId;

  // Check if all selectable sessions are selected
  const allSelected =
    selectableSessions.length > 0 &&
    selectableSessions.every((session) => selectedSessions.has(session));

  const handleDeleteSession = (session: string) => {
    onDeleteSession?.(session);
    // Remove from selected sessions if it was selected
    setSelectedSessions((prev) => {
      const newSet = new Set(prev);
      newSet.delete(session);
      return newSet;
    });
    // Session switching is handled by the store's removeSession
  };

  const handleSessionClick = (session: string) => {
    onSessionSelect?.(session);
  };

  const handleRename = async (sessionId: string, newSessionId: string) => {
    await onRenameSession?.(sessionId, newSessionId);
  };

  const handleSelectAll = () => {
    if (allSelected) {
      // Deselect all
      setSelectedSessions(new Set());
    } else {
      // Select all selectable sessions
      setSelectedSessions(new Set(selectableSessions));
    }
  };

  const handleToggleSession = (session: string) => {
    setSelectedSessions((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(session)) {
        newSet.delete(session);
      } else {
        newSet.add(session);
      }
      return newSet;
    });
  };

  const handleBulkDelete = () => {
    if (selectedSessions.size === 0 || !onBulkDeleteSessions) return;

    const sessionsToDelete = Array.from(selectedSessions);
    const count = sessionsToDelete.length;

    onBulkDeleteSessions(sessionsToDelete, () => {
      // Clear selection after successful deletion
      setSelectedSessions(new Set());
      // Show user-friendly success message
      setSuccessData({
        title: t("chat.sessionsDeletedSuccess", { count }),
      });
    });
  };

  return (
    <div className="flex flex-col pb-4 gap-2">
      <div className="flex flex-col">
        <div className="flex h-4 items-center justify-between">
          <div className="px-2 text-xs font-semibold leading-4 text-muted-foreground">
            {t("chat.sessions")}
          </div>
          <ShadTooltip
            styleClasses="z-50"
            content={t("chat.newChat")}
            side={isShareablePlayground ? "bottom" : "top"}
          >
            <Button
              data-testid="new-chat"
              variant="ghost"
              className="flex h-8 w-8 items-center justify-center !p-0 hover:bg-secondary-hover"
              onClick={onNewChat}
            >
              <ForwardedIconComponent
                name="Plus"
                className="h-[18px] w-[18px] text-ring"
              />
            </Button>
          </ShadTooltip>
        </div>
      </div>
      {sessions.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">
          {t("chat.noSessionsYet")}
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {sessions.map((session, index) => {
            const isFirstNonDefaultSession =
              index > 0 && sessions[index - 1] === currentFlowId;

            return (
              <div key={session}>
                {/* Show Select All controls after the default session.
                    Wrapper is sized + padded to mirror a SessionSelector
                    row (h-8, no extra vertical padding) so the trash
                    button lines up vertically and horizontally with the
                    `⋮` MoreMenu triggers in the session rows below. */}
                {isFirstNonDefaultSession && selectableSessions.length > 0 && (
                  <div className="flex h-8 items-center justify-between">
                    <button
                      type="button"
                      className="flex items-center gap-2 cursor-pointer px-2 bg-transparent border-0 p-0"
                      onClick={handleSelectAll}
                      aria-pressed={allSelected}
                      data-testid="select-all-checkbox"
                    >
                      <div className="flex items-center justify-center w-4 h-4 flex-shrink-0">
                        <ForwardedIconComponent
                          name={allSelected ? "SquareCheck" : "Square"}
                          className={cn(
                            "h-4 w-4",
                            allSelected
                              ? "text-status-red"
                              : "text-muted-foreground",
                          )}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground select-none">
                        {t("chat.selectAll")}
                      </span>
                    </button>
                    {selectedSessions.size > 0 && (
                      <ShadTooltip
                        styleClasses="z-50"
                        content={t("chat.deleteSessionsCount", {
                          count: selectedSessions.size,
                        })}
                        side="top"
                      >
                        <Button
                          data-testid="bulk-delete-button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 p-2 rounded text-status-red hover:text-status-red hover:bg-error-background"
                          onClick={handleBulkDelete}
                        >
                          <ForwardedIconComponent
                            name="Trash2"
                            className="h-4 w-4"
                          />
                        </Button>
                      </ShadTooltip>
                    )}
                  </div>
                )}
                <SessionSelector
                  session={session}
                  currentFlowId={currentFlowId}
                  deleteSession={handleDeleteSession}
                  toggleVisibility={() => handleSessionClick(session)}
                  isVisible={visibleSession === session}
                  updateVisibleSession={handleSessionClick}
                  inspectSession={onOpenLogs}
                  handleRename={handleRename}
                  selectedView={undefined}
                  setSelectedView={() => {}}
                  menuOpen={openMenuSession === session}
                  onMenuOpenChange={(open) => {
                    setOpenMenuSession(open ? session : null);
                  }}
                  isSelected={selectedSessions.has(session)}
                  onToggleSelect={() => handleToggleSession(session)}
                  showCheckbox={selectableSessions.includes(session)}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
