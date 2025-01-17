import { create } from "zustand";

interface PlaygroundStore {
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  onLockChange?: (lock: boolean) => void;
  onMessageUpdate?: (message: string) => void;
  onMessageUpdateError?: (error: string) => void;
  onMessageDelete?: (message: string) => void;
  onMessageDeleteError?: (error: string) => void;
  onFileUploadError?: (error: string) => void;
  setOnMessageUpdate: (callback: (message: string) => void) => void;
  setOnMessageUpdateError: (callback: (error: string) => void) => void;
  setOnMessageDelete: (callback: (message: string) => void) => void;
  setOnMessageDeleteError: (callback: (error: string) => void) => void;
  setOnFileUploadError: (callback: (error: string) => void) => void;
  chatValueStore: string;
  setChatValueStore: (value: string) => void;
  currentFlowId: string;
  setCurrentFlowId: (id: string) => void;
  maxFileSizeUpload: number;
  setMaxFileSizeUpload: (maxFileSizeUpload: number) => void;
  baseUrl: string;
  setBaseUrl: (url: string) => void;
  buildFlow: ({
    startNodeId,
    stopNodeId,
    input_value,
    files,
    silent,
    setLockChat,
    session,
  }: {
    setLockChat?: (lock: boolean) => void;
    startNodeId?: string;
    stopNodeId?: string;
    input_value?: string;
    files?: string[];
    silent?: boolean;
    session?: string;
  }) => Promise<void>;
}

export const usePlaygroundStore = create<PlaygroundStore>((set) => ({
  lockChat: false,
  onLockChange: undefined,
  onMessageUpdate: undefined,
  onMessageUpdateError: undefined,
  onMessageDelete: undefined,
  onMessageDeleteError: undefined,
  onFileUploadError: undefined,
  chatValueStore: "",
  currentFlowId: "",
  maxFileSizeUpload: 100 * 1024 * 1024, // 100MB in bytes
  baseUrl: "",
  setBaseUrl: (url: string) => set({ baseUrl: url }),
  setMaxFileSizeUpload: (maxFileSizeUpload: number) =>
    set({ maxFileSizeUpload: maxFileSizeUpload * 1024 * 1024 }),
  setLockChat: (lock) => {
    set((state) => {
      if (state.onLockChange && state.lockChat !== lock) {
        state.onLockChange(lock);
      }
      return { lockChat: lock };
    });
  },
  setOnMessageUpdate: (callback) => set({ onMessageUpdate: callback }),
  setOnMessageUpdateError: (callback) => set({ onMessageUpdateError: callback }),
  setOnMessageDelete: (callback) => set({ onMessageDelete: callback }),
  setOnMessageDeleteError: (callback) => set({ onMessageDeleteError: callback }),
  setOnFileUploadError: (callback) => set({ onFileUploadError: callback }),
  setChatValueStore: (value: string) => set({ chatValueStore: value }),
  setCurrentFlowId: (id) => set({ currentFlowId: id }),
  buildFlow: async ({
    startNodeId,
    stopNodeId,
    input_value,
    files,
    silent,
    setLockChat,
    session,
  }) => {
    console.log("buildFlow", startNodeId, stopNodeId, input_value, files, silent, setLockChat, session);
  },
}));
