import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface SessionRenameProps {
  sessionId: string;
  onSave: (newSessionId: string) => void;
  onCancel: () => void;
}

export const SessionRename = ({
  sessionId,
  onSave,
  onCancel,
}: SessionRenameProps) => {
  const [editValue, setEditValue] = useState(sessionId);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSave = () => {
    if (editValue.trim() && editValue !== sessionId) {
      onSave(editValue.trim());
    } else {
      onCancel();
    }
  };

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, []);

  return (
    <div className="flex items-center gap-2">
      <Input
        ref={inputRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === "Enter") {
            handleSave();
          } else if (e.key === "Escape") {
            onCancel();
          }
        }}
        className="h-8 text-sm"
      />
      <Button
        size="iconSm"
        variant="ghost"
        onClick={(e) => {
          e.stopPropagation();
          handleSave();
        }}
      >
        <ForwardedIconComponent name="Check" className="h-3 w-3" />
      </Button>
      <Button
        size="iconSm"
        variant="ghost"
        onClick={(e) => {
          e.stopPropagation();
          onCancel();
        }}
      >
        <ForwardedIconComponent name="X" className="h-3 w-3" />
      </Button>
    </div>
  );
};
