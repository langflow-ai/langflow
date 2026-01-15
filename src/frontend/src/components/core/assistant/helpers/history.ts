import { HISTORY_STORAGE_KEY, MAX_HISTORY_SIZE } from "../assistant.constants";

export const getHistory = (): string[] => {
  try {
    const stored = sessionStorage.getItem(HISTORY_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

export const saveToHistory = (input: string): void => {
  const history = getHistory();
  if (history[history.length - 1] !== input) {
    const newHistory = [...history, input].slice(-MAX_HISTORY_SIZE);
    sessionStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(newHistory));
  }
};
