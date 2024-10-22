import IconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import React, { useEffect, useRef, useState } from "react";

export default function SessionSelector({
  deleteSession,
  session,
  toggleVisibility,
  isVisible,
  inspectSession,
  updateVisibleSession,
  selectedView,
  setSelectedView,
}: {
  deleteSession: (session: string) => void;
  session: string;
  toggleVisibility: () => void;
  isVisible: boolean;
  inspectSession: (session: string) => void;
  updateVisibleSession: (session: string) => void;
  selectedView?: { type: string; id: string };
  setSelectedView: (view: { type: string; id: string } | undefined) => void;
}) {
  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSession, setEditedSession] = useState(session);
  const { mutate: updateSessionName } = useUpdateSessionName();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setEditedSession(session);
  }, [session]);

  const handleEditClick = (e?: React.MouseEvent<HTMLDivElement>) => {
    e?.stopPropagation();
    setIsEditing(true);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditedSession(e.target.value);
  };

  const handleConfirm = () => {
    setIsEditing(false);
    if (editedSession.trim() !== session) {
      updateSessionName(
        { old_session_id: session, new_session_id: editedSession.trim() },
        {
          onSuccess: () => {
            if (isVisible) {
              updateVisibleSession(editedSession);
            }
            if (
              selectedView?.type === "Session" &&
              selectedView?.id === session
            ) {
              setSelectedView({ type: "Session", id: editedSession });
            }
          },
        },
      );
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedSession(session);
  };

  const handleSelectChange = (value: string) => {
    switch (value) {
      case "rename":
        handleEditClick();
        break;
      case "messageLogs":
        inspectSession(session);
        break;
      case "delete":
        deleteSession(session);
        break;
    }
  };

  return (
    <div
      data-testid="session-selector"
      onClick={(e) => {
        if (isEditing) e.stopPropagation();
        else toggleVisibility();
      }}
      className={cn(
        "file-component-accordion-div group cursor-pointer rounded-md hover:bg-muted-foreground/30",
        isVisible ? "bg-muted-foreground/15" : "",
      )}
    >
      <div className="flex w-full items-center justify-between gap-2 overflow-hidden border-b px-2 py-3 align-middle">
        <div className="flex min-w-0 items-center gap-2">
          {isEditing ? (
            <div className="flex items-center">
              <Input
                ref={inputRef}
                value={editedSession}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    handleConfirm();
                  }
                }}
                onChange={handleInputChange}
                onBlur={(e) => {
                  console.log(e.relatedTarget);
                  if (
                    !e.relatedTarget ||
                    e.relatedTarget.getAttribute("data-confirm") !== "true"
                  ) {
                    handleCancel();
                  }
                }}
                autoFocus
                className="h-6 flex-grow px-1 py-0"
              />
              <button
                onClick={handleCancel}
                className="hover:text-status-red-hover ml-2 text-status-red"
              >
                <IconComponent name="X" className="h-4 w-4" />
              </button>
              <button
                onClick={handleConfirm}
                data-confirm="true"
                className="ml-2 text-green-500 hover:text-green-600"
              >
                <IconComponent name="Check" className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <ShadTooltip styleClasses="z-50" content={session}>
              <div>
                <Badge
                  variant="gray"
                  size="md"
                  className="block cursor-pointer truncate"
                >
                  {session === currentFlowId ? "Default Session" : session}
                </Badge>
              </div>
            </ShadTooltip>
          )}
        </div>
        <Select value={""} onValueChange={handleSelectChange}>
          <SelectTrigger
            onClick={(e) => {
              e.stopPropagation();
            }}
            onFocusCapture={() => {
              inputRef.current?.focus();
            }}
            data-confirm="true"
            className="h-8 w-8 border-none bg-transparent p-0 focus:ring-0"
          >
            <IconComponent name="MoreHorizontal" className="h-4 w-4" />
          </SelectTrigger>
          <SelectContent side="right" align="start" className="w-40 p-0">
            <SelectItem
              value="rename"
              className="cursor-pointer px-3 py-2 focus:bg-muted"
            >
              <div className="flex items-center">
                <IconComponent name="Pencil" className="mr-2 h-4 w-4" />
                Rename
              </div>
            </SelectItem>
            <SelectItem
              value="messageLogs"
              className="cursor-pointer px-3 py-2 focus:bg-muted"
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center">
                  <IconComponent name="ScrollText" className="mr-2 h-4 w-4" />
                  Message logs
                </div>
                <IconComponent
                  name="ExternalLink"
                  className="absolute right-2 h-4 w-4"
                />
              </div>
            </SelectItem>
            <SelectItem
              value="delete"
              className="cursor-pointer px-3 py-2 focus:bg-muted"
            >
              <div className="flex items-center text-status-red hover:text-status-red">
                <IconComponent name="Trash2" className="mr-2 h-4 w-4" />
                Delete
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
