import { create } from "zustand";

export interface SharedContextEvent {
  operation: "get" | "set" | "append" | "delete" | "keys" | "has_key";
  key: string;
  namespace: string;
  timestamp: string;
  component_id: string;
}

interface SharedContextState {
  events: SharedContextEvent[];
  addEvent: (event: SharedContextEvent) => void;
  clearEvents: () => void;
  getEventsByNamespace: (namespace: string) => SharedContextEvent[];
}

export const useSharedContextStore = create<SharedContextState>((set, get) => ({
  events: [],

  addEvent: (event) => {
    set((state) => ({
      events: [...state.events, event],
    }));
  },

  clearEvents: () => {
    set({ events: [] });
  },

  getEventsByNamespace: (namespace) => {
    return get().events.filter((e) => e.namespace === namespace);
  },
}));
