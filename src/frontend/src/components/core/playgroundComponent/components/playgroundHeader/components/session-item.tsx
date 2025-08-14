import React, { useState } from "react";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useShallow } from "zustand/react/shallow";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { SessionRename } from "./session-rename";

interface SessionItemProps {
  sessionId: string;
  onRename: (oldSessionId: string, newSessionId: string) => void;
  onDelete: (sessionId: string) => void;
}

export const SessionItem = ({
  sessionId,
  onRename,
  onDelete,
}: SessionItemProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const { selectedSession, setSelectedSession } = usePlaygroundStore();

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const handleEditStart = () => {
    setIsEditing(true);
  };

  const handleEditSave = (newSessionId: string) => {
    onRename(sessionId, newSessionId);
    setIsEditing(false);
  };

  const handleEditCancel = () => {
    setIsEditing(false);
  };

  const handleDelete = () => {
    onDelete(sessionId);
    if (selectedSession === sessionId) {
      setSelectedSession(flowId);
    }
  };

  const isSelected = selectedSession === sessionId;

  const canDelete = sessionId !== flowId;

  const handleSessionSelect = () => {
    setSelectedSession(sessionId);
  };

  return (
    <div
      className={cn(
        "flex items-center justify-between p-2 hover:bg-muted cursor-pointer group",
        isSelected && "bg-muted"
      )}
      onClick={handleSessionSelect}
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
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <Button
                size="iconSm"
                variant="ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  handleEditStart();
                }}
                className="h-6 w-6"
              >
                <ForwardedIconComponent name="SquarePen" className="h-3 w-3" />
              </Button>
              {canDelete && (
                <Button
                  size="iconSm"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete();
                  }}
                  className="h-6 w-6 text-muted-foreground hover:text-destructive"
                >
                  <ForwardedIconComponent name="Trash2" className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
