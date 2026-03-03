import { create } from "zustand";

interface AgentBuilderState {
  selectedAgentId: string | null;
  setSelectedAgentId: (id: string | null) => void;
}

const useAgentBuilderStore = create<AgentBuilderState>((set) => ({
  selectedAgentId: null,
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
}));

export default useAgentBuilderStore;
