import { create } from "zustand";
import type {
  SessionInfo,
  SessionManagerStoreType,
} from "@/types/zustand/sessionManager";

const LOCAL_SESSIONS_KEY = (flowId: string) =>
  `langflow_local_sessions_${flowId}`;

function loadLocalSessions(flowId: string): string[] {
  try {
    const stored = window.sessionStorage.getItem(LOCAL_SESSIONS_KEY(flowId));
    return stored ? (JSON.parse(stored) as string[]) : [];
  } catch {
    // silently ignore storage errors
    return [];
  }
}

function saveLocalSessions(flowId: string, sessions: SessionInfo[]) {
  try {
    const localIds = sessions.filter((s) => s.isLocal).map((s) => s.id);
    window.sessionStorage.setItem(
      LOCAL_SESSIONS_KEY(flowId),
      JSON.stringify(localIds),
    );
  } catch {
    // silently ignore storage errors
  }
}

export const useSessionManagerStore = create<SessionManagerStoreType>(
  (set, get) => ({
    flowId: undefined,
    activeSessionId: undefined,
    sessions: [],

    initialize: (flowId: string) => {
      const current = get();
      if (current.flowId === flowId) return;
      // Load local sessions from sessionStorage
      const localIds = loadLocalSessions(flowId);
      const localSessions: SessionInfo[] = localIds.map((id) => ({
        id,
        isLocal: true,
      }));
      set({
        flowId,
        activeSessionId: flowId,
        sessions: localSessions,
      });
    },

    setActiveSessionId: (sessionId: string) => {
      set({ activeSessionId: sessionId });
    },

    addSession: (session: SessionInfo) => {
      const { sessions, flowId } = get();
      if (sessions.some((s) => s.id === session.id)) return;
      const updated = [...sessions, session];
      set({ sessions: updated });
      if (flowId) saveLocalSessions(flowId, updated);
    },

    removeSession: (sessionId: string) => {
      const { sessions, activeSessionId, flowId } = get();
      const updated = sessions.filter((s) => s.id !== sessionId);
      const newState: Partial<SessionManagerStoreType> = { sessions: updated };
      if (activeSessionId === sessionId) {
        newState.activeSessionId = flowId;
      }
      set(newState);
      if (flowId) saveLocalSessions(flowId, updated);
    },

    renameSession: (oldId: string, newId: string) => {
      const { sessions, activeSessionId, flowId } = get();
      const updated = sessions.map((s) =>
        s.id === oldId ? { ...s, id: newId } : s,
      );
      const newState: Partial<SessionManagerStoreType> = { sessions: updated };
      if (activeSessionId === oldId) {
        newState.activeSessionId = newId;
      }
      set(newState);
      if (flowId) saveLocalSessions(flowId, updated);
    },

    syncFromServer: (serverSessionIds: string[]) => {
      const { sessions, flowId } = get();
      const serverSet = new Set(serverSessionIds);

      const merged: SessionInfo[] = [];
      const seen = new Set<string>();

      // Keep existing sessions in their current order, promoting local→server
      for (const s of sessions) {
        if (seen.has(s.id)) continue;
        seen.add(s.id);
        if (serverSet.has(s.id)) {
          // Promote: was local, now on server
          merged.push({ id: s.id, isLocal: false });
        } else if (s.isLocal) {
          // Still local-only, keep
          merged.push(s);
        }
        // If not on server and not local, it was removed server-side — drop it
      }

      // Add new server sessions not already tracked
      for (const id of serverSessionIds) {
        if (seen.has(id)) continue;
        // Skip the flowId itself — it's the default session, not in the list
        if (id === flowId) continue;
        seen.add(id);
        merged.push({ id, isLocal: false });
      }

      set({ sessions: merged });
      if (flowId) saveLocalSessions(flowId, merged);
    },

    getOrderedSessionIds: () => {
      const { flowId, sessions } = get();
      const ids: string[] = [];
      if (flowId) ids.push(flowId);
      for (const s of sessions) {
        if (s.id !== flowId) ids.push(s.id);
      }
      return ids;
    },

    reset: () => {
      set({
        flowId: undefined,
        activeSessionId: undefined,
        sessions: [],
      });
    },
  }),
);
