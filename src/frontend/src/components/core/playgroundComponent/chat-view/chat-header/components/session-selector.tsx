import type React from "react";
import { useState } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { useVoiceStore } from "@/stores/voiceStore";
import { cn } from "@/utils/utils";
import { SessionMoreMenu } from "./session-more-menu";
import { SessionRename } from "./session-rename";

export interface SessionSelectorProps {
  session: string;
  currentFlowId: string;
  deleteSession: (session: string) => void;
  toggleVisibility: () => void;
  isVisible: boolean;
  inspectSession?: (session: string) => void;
  updateVisibleSession: (session: string) => void;
  selectedView?: { type: string; id: string };
  setSelectedView?: (view: { type: string; id: string } | undefined) => void;
  playgroundPage?: boolean;
  setActiveSession?: (session: string) => void;
}

export function SessionSelector({
  session,
  currentFlowId,
  deleteSession,
  toggleVisibility,
  isVisible,
  inspectSession,
  updateVisibleSession,
  selectedView,
  setSelectedView,
  playgroundPage = false,
  setActiveSession,
}: SessionSelectorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const { mutate: updateSessionName } = useUpdateSessionName();
  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );

  const handleEditClick = (e?: React.MouseEvent<HTMLDivElement>) => {
    e?.stopPropagation();
    setIsEditing(true);
  };

  const handleRenameSave = (newSessionId: string) => {
    setIsEditing(false);
    if (newSessionId.trim() !== session && newSessionId.trim()) {
      updateSessionName(
        { old_session_id: session, new_session_id: newSessionId.trim() },
        {
          onSuccess: () => {
            if (isVisible) {
              updateVisibleSession(newSessionId.trim());
            }
            if (
              selectedView?.type === "Session" &&
              selectedView?.id === session &&
              setSelectedView
            ) {
              setSelectedView({ type: "Session", id: newSessionId.trim() });
            }
          },
        },
      );
    }
  };

  const handleRename = () => {
    handleEditClick();
  };

  const handleMessageLogs = () => {
    inspectSession?.(session);
  };

  const handleDelete = () => {
    deleteSession(session);
  };

  return (
    <div
      data-testid="session-selector"
      onClick={(e) => {
        setNewSessionCloseVoiceAssistant(true);
        if (isEditing) e.stopPropagation();
        else toggleVisibility();
      }}
      className={cn(
        "file-component-accordion-div group cursor-pointer rounded-md text-left text-mmd hover:bg-accent",
        isVisible ? "bg-accent font-semibold" : "font-normal",
      )}
    >
      <div className="flex w-full items-center justify-between overflow-hidden px-2 py-1 align-middle">
        <div className="flex w/full min-w-0 items-center">
          {isEditing ? (
            <SessionRename sessionId={session} onSave={handleRenameSave} />
          ) : (
            <ShadTooltip styleClasses="z-50" content={session}>
              <div className="relative w-full overflow-hidden">
                <span className="w-full truncate bg-transparent">
                  {session === currentFlowId ? "Default Session" : session}
                </span>
              </div>
            </ShadTooltip>
          )}
        </div>
        <SessionMoreMenu
          onRename={handleRename}
          onMessageLogs={handleMessageLogs}
          onDelete={handleDelete}
          showMessageLogs={!!inspectSession}
          side="right"
          align="start"
          isVisible={isVisible}
          tooltipContent="Options"
          tooltipSide="right"
          triggerClassName="w-fit"
        />
      </div>
    </div>
  );
}
