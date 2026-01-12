import React, { useState } from "react";
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

  const handleEditClick = () => {
    setIsEditing(true);
  };

  const handleRenameSave = (newSessionId: string) => {
    setIsEditing(false);
    const trimmed = newSessionId.trim();
    if (!trimmed || trimmed === session) return;
    updateSessionName(
      { old_session_id: session, new_session_id: trimmed },
      {
        onSuccess: () => {
          if (isVisible) {
            updateVisibleSession(trimmed);
          }
          if (
            selectedView?.type === "Session" &&
            selectedView?.id === session &&
            setSelectedView
          ) {
            setSelectedView({ type: "Session", id: trimmed });
          }
        },
      },
    );
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
      <div className="flex w-full items-center justify-between overflow-hidden p-2 align-middle w-218">
        <div className="flex w/full min-w-0 items-center">
          {isEditing ? (
            <div
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              onMouseUp={(e) => e.stopPropagation()}
              className="w-full"
            >
              <SessionRename
                sessionId={session}
                onSave={handleRenameSave}
                onDone={() => {
                  setIsEditing(false);
                }}
              />
            </div>
          ) : (
            <ShadTooltip styleClasses="z-50" content={session}>
              <div className="relative w-full overflow-hidden">
                <span className="w-full truncate bg-transparent text-mmd">
                  {session === currentFlowId ? "Default Session" : session}
                </span>
              </div>
            </ShadTooltip>
          )}
        </div>

        <SessionMoreMenu
          onRename={handleEditClick}
          onMessageLogs={() => inspectSession?.(session)}
          onDelete={() => deleteSession(session)}
          showDelete={session !== currentFlowId}
          side="bottom"
          align="end"
          sideOffset={4}
          contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
          isVisible={true}
          tooltipContent="More options"
          tooltipSide="left"
        />
      </div>
    </div>
  );
}
