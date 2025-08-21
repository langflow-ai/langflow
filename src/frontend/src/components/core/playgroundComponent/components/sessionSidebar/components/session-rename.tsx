import type React from "react";
import { Input } from "@/components/ui/input";
import { MenuIconButton } from "./menu-icon-button";

interface SessionRenameProps {
  sessionId: string;
  onSave: (newSessionId: string) => void;
}

export const SessionRename = ({ sessionId, onSave }: SessionRenameProps) => {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const formData = new FormData(e.currentTarget);
    const newSessionId = formData.get("sessionId") as string;
    const trimmedValue = newSessionId?.trim();

    if (trimmedValue) {
      onSave(trimmedValue);
    }
    onSave(sessionId);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.key === "Escape") {
      onSave(sessionId);
    }
  };

  const handleClick = (
    e: React.MouseEvent<HTMLInputElement | HTMLButtonElement>
  ) => {
    e.stopPropagation();
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.stopPropagation();
    onSave(e.currentTarget.value);
  };

  const handleCancel = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onSave(sessionId);
  };

  const handleSubmitMouseDown = (e: React.MouseEvent<HTMLButtonElement>) => {
    // prevents blurring the input on mouse down
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-1">
      <Input
        name="sessionId"
        defaultValue={sessionId}
        autoFocus
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        className="h-8 text-mmd border-none bg-transparent p-0 w-full"
        required
      />
      <MenuIconButton
        icon="Check"
        type="submit"
        onMouseDown={handleSubmitMouseDown}
      />
      <MenuIconButton icon="X" onClick={handleCancel} />
    </form>
  );
};
