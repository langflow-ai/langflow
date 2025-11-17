import { useCallback, useState } from "react";
import { v4 as uuid } from "uuid";

export type ThreadLog = {
  id: string;
  createdAt: number;
  messagesCount: number;
};

const STORAGE_KEY = "marketplace_thread_logs";

function loadLogs(): ThreadLog[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ThreadLog[]) : [];
  } catch {
    return [];
  }
}

function saveLogs(logs: ThreadLog[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(logs));
  } catch {
    // ignore storage errors
  }
}

export function useThreadManager() {
  const [currentThreadId, setCurrentThreadId] = useState<string>(() => uuid());
  const [threadLogs, setThreadLogs] = useState<ThreadLog[]>(() => loadLogs());

  const newThread = useCallback((prevMessagesCount: number = 0) => {
    setThreadLogs((prev) => {
      const updated = [
        { id: currentThreadId, createdAt: Date.now(), messagesCount: prevMessagesCount },
        ...prev,
      ].slice(0, 100);
      saveLogs(updated);
      return updated;
    });

    const nextId = uuid();
    setCurrentThreadId(nextId);
    return nextId;
  }, [currentThreadId]);

  const clearLogs = useCallback(() => {
    setThreadLogs([]);
    saveLogs([]);
  }, []);

  return { currentThreadId, threadLogs, newThread, clearLogs };
}