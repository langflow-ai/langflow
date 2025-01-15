import { create } from "zustand";

interface PlaygroundStore {
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  onLockChange?: (lock: boolean) => void;
  chatValueStore: string;
  setChatValueStore: (value: string) => void;
  currentFlowId: string;
  setCurrentFlowId: (id: string) => void;
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
  chatValueStore: "",
  currentFlowId: "",
  setLockChat: (lock) => {
    set((state) => {
      if (state.onLockChange && state.lockChat !== lock) {
        state.onLockChange(lock);
      }
      return { lockChat: lock };
    });
  },
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
