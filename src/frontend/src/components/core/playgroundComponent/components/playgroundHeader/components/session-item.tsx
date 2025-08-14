import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

interface SessionItemProps {
  sessionId: string;
  isSelected: boolean;
  canDelete: boolean;
  onSelect: (sessionId: string) => void;
  onRename: (oldSessionId: string, newSessionId: string) => void;
  onDelete: (sessionId: string) => void;
}

export const SessionItem = ({
  sessionId,
  isSelected,
  canDelete,
  onSelect,
  onRename,
  onDelete,
}: SessionItemProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleEditStart = () => {
    setIsEditing(true);
    setEditValue(sessionId);
  };

  const handleEditSave = () => {
    if (editValue.trim() && editValue !== sessionId) {
      onRename(sessionId, editValue.trim());
    }
    setIsEditing(false);
    setEditValue("");
  };

  const handleEditCancel = () => {
    setIsEditing(false);
    setEditValue("");
  };

  const handleDelete = () => {
    onDelete(sessionId);
  };

  const handleSessionSelect = () => {
    onSelect(sessionId);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

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
          <div className="flex items-center gap-2">
            <Input
              ref={inputRef}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") {
                  handleEditSave();
                } else if (e.key === "Escape") {
                  handleEditCancel();
                }
              }}
              className="h-8 text-sm"
            />
            <Button
              size="iconSm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                handleEditSave();
              }}
            >
              <ForwardedIconComponent name="Check" className="h-3 w-3" />
            </Button>
            <Button
              size="iconSm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                handleEditCancel();
              }}
            >
              <ForwardedIconComponent name="X" className="h-3 w-3" />
            </Button>
          </div>
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
