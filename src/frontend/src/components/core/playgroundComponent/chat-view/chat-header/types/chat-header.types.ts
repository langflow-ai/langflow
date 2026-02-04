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
  renameLocalSession?: (oldSessionId: string, newSessionId: string) => void;
}
