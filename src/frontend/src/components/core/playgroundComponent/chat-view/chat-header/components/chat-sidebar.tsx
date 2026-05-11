import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import useAlertStore from "@/stores/alertStore";
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
        title: `${count} session${count > 1 ? "s" : ""} deleted successfully`,
      });
    });
  };

  return (
    <div className="flex flex-col pb-4 gap-2">
      <div className="flex flex-col">
        <div className="flex h-4 items-center justify-between">
          <div className="px-2 text-xs font-semibold leading-4 text-muted-foreground">
            Sessions
          </div>
          <ShadTooltip
            styleClasses="z-50"
            content="New Chat"
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
          No sessions yet.
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {sessions.map((session, index) => {
            const isDefaultSession = session === currentFlowId;
            const isFirstNonDefaultSession =
              index > 0 && sessions[index - 1] === currentFlowId;

            return (
              <div key={session}>
                {/* Show Select All controls after the default session */}
                {isFirstNonDefaultSession && selectableSessions.length > 0 && (
                  <div className="flex items-center justify-between px-2 py-1 mb-1">
                    <div
                      className="flex items-center gap-2 cursor-pointer"
                      onClick={handleSelectAll}
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
                        Select All
                      </span>
                    </div>
                    <div className="w-8 h-8 flex items-center justify-center">
                      {selectedSessions.size > 0 && (
                        <ShadTooltip
                          styleClasses="z-50"
                          content={`Delete ${selectedSessions.size} session${selectedSessions.size > 1 ? "s" : ""}`}
                          side="top"
                        >
                          <Button
                            data-testid="bulk-delete-button"
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-status-red hover:text-status-red hover:bg-error-background"
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
