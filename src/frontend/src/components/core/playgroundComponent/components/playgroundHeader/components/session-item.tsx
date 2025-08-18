import { useState } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import { SessionRename } from "./session-rename";

interface SessionItemProps {
  sessionId: string;
  onRename: (oldSessionId: string, newSessionId: string) => void;
  onDelete: (sessionId: string) => void;
  tabIndex: number;
}

export const SessionItem = ({
  sessionId,
  onRename,
  onDelete,
  tabIndex,
}: SessionItemProps) => {
  const [isEditing, setIsEditing] = useState(false);

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const handleEditSave = (newSessionId: string) => {
    if (!newSessionId.trim()) {
      setIsEditing(false);
      return;
    }
    onRename(sessionId, newSessionId);
    setIsEditing(false);
  };

  const handleEditStart = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setIsEditing(true);
  };

  const handleEditCancel = () => {
    setIsEditing(false);
  };

  const handleDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onDelete(sessionId);
    if (selectedSession === sessionId) {
      setSelectedSession(flowId);
    }
  };

  const handleSessionSelect = () => {
    setSelectedSession(sessionId);
  };

  const handleSessionSelectKeyDown = (
    e: React.KeyboardEvent<HTMLDivElement>
  ) => {
    if (e.key === "Enter" || e.key === " ") {
      handleSessionSelect();
    }
  };

  const isSelected = selectedSession === sessionId;

  const canEdit = sessionId !== flowId;

  return (
    // biome-ignore lint/a11y/useSemanticElements: Button inside this div already is a <button> element, so we can't nest them.
    <div
      className={cn(
        "flex items-center justify-between p-2 hover:bg-muted cursor-pointer group",
        isSelected && "bg-muted"
      )}
      onClick={handleSessionSelect}
      onKeyDown={handleSessionSelectKeyDown}
      aria-label={`Select session ${sessionId}`}
      role="button"
      tabIndex={tabIndex}
    >
      <div className="flex-1 min-w-0">
        {isEditing ? (
          <SessionRename
            sessionId={sessionId}
            onSave={handleEditSave}
            onCancel={handleEditCancel}
          />
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-sm truncate font-medium">{sessionId}</span>
            {canEdit && (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  size="iconSm"
                  variant="ghost"
                  onClick={handleEditStart}
                  className="h-6 w-6"
                >
                  <ForwardedIconComponent
                    name="SquarePen"
                    className="h-3 w-3"
                  />
                </Button>
                <Button
                  size="iconSm"
                  variant="ghost"
                  onClick={handleDelete}
                  className="h-6 w-6 text-muted-foreground hover:text-destructive"
                >
                  <ForwardedIconComponent name="Trash2" className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
