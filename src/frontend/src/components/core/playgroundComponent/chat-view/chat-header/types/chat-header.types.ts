import type { RefObject } from "react";

export interface ChatHeaderProps {
  sessions: string[];
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  currentFlowId?: string;
  onToggleFullscreen?: () => void;
  isFullscreen?: boolean;
  onDeleteSession?: (sessionId: string) => void;
  onClose?: () => void;
  className?: string;
  openLogsModal?: boolean;
  setOpenLogsModal?: (open: boolean) => void;
  logsModalTriggerRef?: RefObject<HTMLElement | null>;
  onRenameSession?: (oldId: string, newId: string) => Promise<void>;
  onClearChat?: () => void;
}
