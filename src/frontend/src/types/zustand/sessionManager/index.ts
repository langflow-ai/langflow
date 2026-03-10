export interface SessionInfo {
  id: string;
  isLocal: boolean;
}

export type SessionManagerStoreType = {
  // State
  flowId: string | undefined;
  activeSessionId: string | undefined;
  sessions: SessionInfo[];

  // Actions (pure state transitions — no side effects)
  initialize: (flowId: string) => void;
  setActiveSessionId: (sessionId: string) => void;
  addSession: (session: SessionInfo) => void;
  removeSession: (sessionId: string) => void;
  renameSession: (oldId: string, newId: string) => void;
  syncFromServer: (serverSessionIds: string[]) => void;
  getOrderedSessionIds: () => string[];
  reset: () => void;
};
