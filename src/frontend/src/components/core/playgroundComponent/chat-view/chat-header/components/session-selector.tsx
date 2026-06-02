import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { useVoiceStore } from "@/stores/voiceStore";
import { cn } from "@/utils/utils";
import { useSessionHasMessages } from "../hooks/use-session-has-messages";
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
  handleRename?: (oldSessionId: string, newSessionId: string) => Promise<void>;
  menuOpen?: boolean;
  onMenuOpenChange?: (open: boolean) => void;
  isSelected?: boolean;
  onToggleSelect?: () => void;
  showCheckbox?: boolean;
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
  handleRename,
  menuOpen,
  onMenuOpenChange,
  isSelected = false,
  onToggleSelect,
  showCheckbox = false,
}: SessionSelectorProps) {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const { mutate: updateSessionName } = useUpdateSessionName();
  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );

  const handleEditClick = () => {
    setIsEditing(true);
  };

  const handleRenameSave = async (newSessionId: string) => {
    setIsEditing(false);
    const trimmed = newSessionId.trim();
    if (!trimmed || trimmed === session) return;

    // Use handleRename if provided (from sidebar), otherwise use mutation directly (from header)
    if (handleRename) {
      await handleRename(session, trimmed);
      updateVisibleSession(trimmed);
      if (
        selectedView?.type === "Session" &&
        selectedView?.id === session &&
        setSelectedView
      ) {
        setSelectedView({ type: "Session", id: trimmed });
      }
    } else {
      // Wait for the mutation to complete before updating visible session
      await updateSessionName(
        { old_session_id: session, new_session_id: trimmed },
        {
          onSuccess: () => {
            // Update visible session after rename is complete
            updateVisibleSession(trimmed);
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
    }
  };

  // Default session (flowId) cannot be renamed, but can be deleted if it has messages
  const isDefaultSession = session === currentFlowId;

  const hasMessages = useSessionHasMessages({
    sessionId: session,
    flowId: currentFlowId,
  });

  const canModifySession = !isDefaultSession;
  const canDeleteSession = hasMessages || !isDefaultSession;
  const canRenameSession = canModifySession && hasMessages;

  return (
    <div
      data-testid="session-selector"
      data-active={isVisible ? "true" : undefined}
      aria-current={isVisible ? "page" : undefined}
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
      <div className="flex h-8 items-center justify-between overflow-hidden w-full">
        <div className="flex w-full min-w-0 items-center gap-2 px-2">
          {showCheckbox && onToggleSelect && (
            <div
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect();
              }}
              className="cursor-pointer flex items-center justify-center w-4 h-8 flex-shrink-0"
              data-testid={`session-${session}-checkbox`}
            >
              {/* The 16x16 column is always reserved so the row layout
                  does not jump. The icon itself is hidden by default and
                  revealed on row hover (via the row's `group` class).
                  A checked box stays visible regardless so users can see
                  their selection without re-hovering each row.
                  `invisible` (visibility: hidden) also disables pointer
                  events so stray clicks on the hidden column cannot
                  toggle selection. */}
              <ForwardedIconComponent
                name={isSelected ? "SquareCheck" : "Square"}
                className={cn(
                  "h-4 w-4 transition-opacity",
                  isSelected
                    ? "text-status-red"
                    : "text-muted-foreground invisible group-hover:visible",
                )}
              />
            </div>
          )}
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
                  {isDefaultSession ? t("chat.defaultSession") : session}
                </span>
              </div>
            </ShadTooltip>
          )}
        </div>

        <SessionMoreMenu
          onRename={handleEditClick}
          onMessageLogs={() => inspectSession?.(session)}
          onDelete={() => deleteSession(session)}
          showRename={canRenameSession}
          showDelete={canDeleteSession}
          side="bottom"
          align="end"
          dataTestid={`session-${session}-more-menu`}
          sideOffset={4}
          contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
          isVisible={true}
          tooltipContent={t("playgroundComponent.moreOptions")}
          tooltipSide="left"
          open={menuOpen}
          onOpenChange={onMenuOpenChange}
          isDefaultSession={isDefaultSession}
        />
      </div>
    </div>
  );
}
