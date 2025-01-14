export type ChatViewWrapperProps = {
    selectedViewField: { type: string; id: string } | undefined;
    visibleSession: string | undefined;
    sessions: string[];
    sidebarOpen: boolean;
    currentFlowId: string;
    setSidebarOpen: (open: boolean) => void;
    setvisibleSession: (session: string | undefined) => void;
    setSelectedViewField: (
      field: { type: string; id: string } | undefined,
    ) => void;
    haveChat: { type: string; id: string; displayName: string } | undefined;
    messagesFetched: boolean;
    sessionId: string;
    sendMessage: (options: { repeat: number; files?: string[] }) => Promise<void>;
    lockChat: boolean;
    setLockChat: (locked: boolean) => void;
  };
