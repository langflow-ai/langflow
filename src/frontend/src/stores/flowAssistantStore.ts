import { create } from "zustand";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";

export type ToolCallDetail = {
  name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
  error?: string | null;
  status?: "pending" | "running" | "done" | "error";
};

export type ReasoningBlock = {
  content: string;
  summary?: string;
};

export type TextSegment = {
  type: "text";
  content: string;
};

export type ToolCallSegment = {
  type: "tool_call";
  toolCall: ToolCallDetail;
};

export type ReasoningSegment = {
  type: "reasoning";
  reasoning: ReasoningBlock;
};

export type MessageSegment = TextSegment | ToolCallSegment | ReasoningSegment;

export type FlowAssistantChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  toolCalls?: ToolCallDetail[];
  segments?: MessageSegment[];
  isStreaming?: boolean;
  reasoningBlocks?: ReasoningBlock[];
};

type FlowAssistantState = {
  isOpen: boolean;
  messages: FlowAssistantChatMessage[];
  isStreaming: boolean;
  selectedModel: string;
  toggle: () => void;
  close: () => void;
  open: () => void;
  clear: () => void;
  addMessage: (m: Omit<FlowAssistantChatMessage, "id">) => string;
  updateMessage: (
    id: string,
    updates: Partial<FlowAssistantChatMessage>,
  ) => void;
  appendToMessage: (id: string, text: string) => void;
  addToolCallToMessage: (id: string, tc: ToolCallDetail) => void;
  updateLastToolCall: (id: string, updates: Partial<ToolCallDetail>) => void;
  addReasoningToMessage: (id: string, reasoning: ReasoningBlock) => void;
  setStreaming: (v: boolean) => void;
  setSelectedModel: (model: string) => void;
};

let msgIdCounter = 0;

const STORAGE_KEY = "langflow-flow-assistant-selected-model";

export const useFlowAssistantStore = create<FlowAssistantState>((set) => ({
  isOpen: false,
  messages: [],
  isStreaming: false,
  selectedModel: (() => {
    const stored = getLocalStorage(STORAGE_KEY);
    return stored || "";
  })(),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  close: () => set({ isOpen: false }),
  open: () => set({ isOpen: true }),
  clear: () => set({ messages: [], isStreaming: false }),
  setStreaming: (v) => set({ isStreaming: v }),
  setSelectedModel: (model: string) => {
    set({ selectedModel: model });
    setLocalStorage(STORAGE_KEY, model);
  },
  addMessage: (m) => {
    const id = `msg-${++msgIdCounter}`;
    set((s) => ({
      messages: [...s.messages, { ...m, id }],
    }));
    return id;
  },
  updateMessage: (id, updates) =>
    set((s) => ({
      messages: s.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg,
      ),
    })),
  appendToMessage: (id, text) =>
    set((s) => ({
      messages: s.messages.map((msg) => {
        if (msg.id !== id) return msg;
        const newContent = msg.content + text;
        const segments = [...(msg.segments ?? [])];
        const lastSegment = segments[segments.length - 1];
        if (lastSegment && lastSegment.type === "text") {
          segments[segments.length - 1] = {
            ...lastSegment,
            content: lastSegment.content + text,
          };
        } else {
          segments.push({ type: "text", content: text });
        }
        return { ...msg, content: newContent, segments };
      }),
    })),
  addToolCallToMessage: (id, tc) =>
    set((s) => ({
      messages: s.messages.map((msg) => {
        if (msg.id !== id) return msg;
        const toolCalls = [...(msg.toolCalls ?? []), tc];
        const segments: MessageSegment[] = [
          ...(msg.segments ?? []),
          { type: "tool_call", toolCall: tc },
        ];
        return { ...msg, toolCalls, segments };
      }),
    })),
  updateLastToolCall: (id, updates) =>
    set((s) => ({
      messages: s.messages.map((msg) => {
        if (msg.id !== id || !msg.toolCalls?.length) return msg;
        const toolCalls = [...msg.toolCalls];
        toolCalls[toolCalls.length - 1] = {
          ...toolCalls[toolCalls.length - 1],
          ...updates,
        };
        const segments = [...(msg.segments ?? [])];
        for (let i = segments.length - 1; i >= 0; i--) {
          if (segments[i].type === "tool_call") {
            segments[i] = {
              type: "tool_call",
              toolCall: {
                ...(segments[i] as ToolCallSegment).toolCall,
                ...updates,
              },
            };
            break;
          }
        }
        return { ...msg, toolCalls, segments };
      }),
    })),
  addReasoningToMessage: (id, reasoning) =>
    set((s) => ({
      messages: s.messages.map((msg) => {
        if (msg.id !== id) return msg;
        const reasoningBlocks = [...(msg.reasoningBlocks ?? []), reasoning];
        const segments: MessageSegment[] = [
          ...(msg.segments ?? []),
          { type: "reasoning", reasoning },
        ];
        return { ...msg, reasoningBlocks, segments };
      }),
    })),
}));
