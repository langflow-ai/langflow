import type React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const formData = new FormData(e.currentTarget);
    const newSessionId = formData.get("sessionId") as string;
    const trimmedValue = newSessionId?.trim();

    if (trimmedValue && trimmedValue !== sessionId) {
      onSave(trimmedValue);
    } else {
      onCancel();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.key === "Escape") {
      onCancel();
    }
  };

  const handleClick = (
    e: React.MouseEvent<HTMLInputElement | HTMLButtonElement>
  ) => {
    e.stopPropagation();
  };

  const handleCancel = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onCancel();
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <Input
        name="sessionId"
        defaultValue={sessionId}
        autoFocus
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        className="h-8 text-sm"
        required
      />
      <Button type="submit" size="iconSm" variant="ghost" onClick={handleClick}>
        <ForwardedIconComponent name="Check" className="h-3 w-3" />
      </Button>
      <Button
        type="button"
        size="iconSm"
        variant="ghost"
        onClick={handleCancel}
      >
        <ForwardedIconComponent name="X" className="h-3 w-3" />
      </Button>
    </form>
  );
};
