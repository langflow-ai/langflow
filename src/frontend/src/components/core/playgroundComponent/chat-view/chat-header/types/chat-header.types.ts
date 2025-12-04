export interface ChatHeaderProps {
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  currentFlowId?: string;
  onToggleFullscreen?: () => void;
  isFullscreen?: boolean;
  onDeleteSession?: (sessionId: string) => void;
  onClose?: () => void;
  className?: string;
}
