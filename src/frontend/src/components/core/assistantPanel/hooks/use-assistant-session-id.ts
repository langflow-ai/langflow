import { useCallback, useEffect, useState } from "react";
import {
  getLocalStorage,
  removeLocalStorage,
  setLocalStorage,
} from "@/utils/local-storage-util";
import { ASSISTANT_SESSION_STORAGE_KEY_PREFIX } from "../assistant-panel.constants";

interface UseAssistantSessionIdReturn {
  sessionId: string;
  resetSessionId: () => void;
}

function buildStorageKey(flowId: string): string {
  return `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}${flowId}`;
}

function getOrCreateSessionId(flowId: string): string {
  const storageKey = buildStorageKey(flowId);
  const stored = getLocalStorage(storageKey);

  if (stored) {
    return stored;
  }

  const newId = crypto.randomUUID();
  setLocalStorage(storageKey, newId);
  return newId;
}

export function useAssistantSessionId(
  flowId: string,
): UseAssistantSessionIdReturn {
  const [sessionId, setSessionId] = useState<string>(() =>
    getOrCreateSessionId(flowId),
  );

  useEffect(() => {
    setSessionId(getOrCreateSessionId(flowId));
  }, [flowId]);

  const resetSessionId = useCallback(() => {
    const storageKey = buildStorageKey(flowId);
    removeLocalStorage(storageKey);
    const newId = crypto.randomUUID();
    setLocalStorage(storageKey, newId);
    setSessionId(newId);
  }, [flowId]);

  return { sessionId, resetSessionId };
}
