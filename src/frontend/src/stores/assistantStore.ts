import { create } from "zustand";
import type {
  AssistantMessage,
  AssistantMessageMetadata,
  AssistantMessageType,
  ProgressMetadata,
} from "@/components/core/assistant/assistant.types";

const DEFAULT_MAX_RETRIES = 3;
const STORAGE_KEY = "assistant-max-retries";
const MODEL_STORAGE_KEY = "assistant-selected-model";

const getStoredMaxRetries = (): number => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) {
      const value = parseInt(stored, 10);
      if (!isNaN(value) && value >= 0 && value <= 5) {
        return value;
      }
    }
  } catch {
    // localStorage not available
  }
  return DEFAULT_MAX_RETRIES;
};

const getStoredModel = (): string | null => {
  try {
    return localStorage.getItem(MODEL_STORAGE_KEY);
  } catch {
    return null;
  }
};

// Re-export types for consumers that import from this file
export type { AssistantMessageType, ProgressMetadata, AssistantMessageMetadata };

// Alias for backward compatibility
export type AssistantMessageData = AssistantMessage;

type AssistantStoreType = {
  isTerminalOpen: boolean;
  maxRetries: number;
  scrollPosition: number;
  messages: AssistantMessageData[];
  selectedModel: string | null;
  setTerminalOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setMaxRetries: (value: number) => void;
  setScrollPosition: (position: number) => void;
  setMessages: (messages: AssistantMessageData[]) => void;
  addMessage: (message: AssistantMessageData) => void;
  clearMessages: () => void;
  setSelectedModel: (model: string) => void;
};

export const useAssistantStore = create<AssistantStoreType>((set) => ({
  isTerminalOpen: false,
  maxRetries: getStoredMaxRetries(),
  scrollPosition: -1, // -1 means "scroll to bottom"
  messages: [],
  selectedModel: getStoredModel(),
  setTerminalOpen: (open) => set({ isTerminalOpen: open }),
  toggleTerminal: () => set((state) => ({ isTerminalOpen: !state.isTerminalOpen })),
  setMaxRetries: (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, value.toString());
    } catch {
      // localStorage not available
    }
    set({ maxRetries: value });
  },
  setScrollPosition: (position) => set({ scrollPosition: position }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  clearMessages: () => set({ messages: [] }),
  setSelectedModel: (model) => {
    try {
      localStorage.setItem(MODEL_STORAGE_KEY, model);
    } catch {
      // localStorage not available
    }
    set({ selectedModel: model });
  },
}));
