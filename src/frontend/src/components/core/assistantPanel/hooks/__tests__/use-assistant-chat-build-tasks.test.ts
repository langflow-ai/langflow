import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * F2 — TaskList inline build progress.
 *
 * Every incremental canvas mutation (add/remove/connect/configure) emits an
 * SSE event the hook already processes for the canvas. We now also append a
 * structured ``BuildTask`` entry on the assistant message so the chat can
 * render a live checklist of what the agent did. The structured form lets
 * the UI show "Adding ChatInput ✓" → "Wiring ChatInput→Agent ✓" without
 * scraping the markdown content the LLM emits.
 */

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => {},
}));

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => jest.fn(),
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
  return { __esModule: true, default: fn };
});

const mockSetNodes = jest.fn();
const mockSetEdges = jest.fn();
jest.mock("@/stores/flowStore", () => {
  const state = {
    setNodes: (...args: unknown[]) => mockSetNodes(...args),
    setEdges: (...args: unknown[]) => mockSetEdges(...args),
    paste: jest.fn(),
  };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

jest.mock("short-unique-id", () => {
  let counter = 0;
  return class ShortUniqueId {
    randomUUID() {
      counter += 1;
      return `mock-uid-${counter}`;
    }
  };
});

const TEST_MODEL = {
  id: "openai/gpt-4",
  name: "gpt-4",
  provider: "openai",
  displayName: "GPT-4",
};

describe("useAssistantChat — build task list", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPostAssistStream.mockResolvedValue(undefined);
  });

  describe("appends BuildTask entries per canvas action", () => {
    it("should_append_a_build_task_when_add_component_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "ChatInput-abc" },
            component_type: "ChatInput",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("add chatinput", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(1);
      expect(msg?.buildTasks?.[0]).toMatchObject({
        action: "add_component",
        componentId: "ChatInput-abc",
        componentType: "ChatInput",
      });
    });

    it("should_append_a_build_task_when_remove_component_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "remove_component",
            component_id: "ChatInput-abc",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("remove it", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(1);
      expect(msg?.buildTasks?.[0]).toMatchObject({
        action: "remove_component",
        componentId: "ChatInput-abc",
      });
    });

    it("should_append_a_build_task_when_connect_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "connect",
            source_id: "ChatInput-abc",
            target_id: "Agent-xyz",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("wire them", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(1);
      expect(msg?.buildTasks?.[0]).toMatchObject({
        action: "connect",
        sourceId: "ChatInput-abc",
        targetId: "Agent-xyz",
      });
    });

    it("should_append_a_build_task_when_configure_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "configure",
            component_id: "Agent-xyz",
            params: { temperature: 0.5 },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("set temp", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(1);
      expect(msg?.buildTasks?.[0]).toMatchObject({
        action: "configure",
        componentId: "Agent-xyz",
      });
    });
  });

  describe("dedup", () => {
    it("should_not_duplicate_when_same_action_and_component_arrive_twice", async () => {
      // Backend may emit a repeat (e.g., retry, re-emission). The chat
      // should show one entry per logical operation.
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "ChatInput-abc" },
            component_type: "ChatInput",
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "ChatInput-abc" },
            component_type: "ChatInput",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("add chatinput", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(1);
    });

    it("should_keep_different_components_as_separate_tasks", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "ChatInput-abc" },
            component_type: "ChatInput",
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "Agent-xyz" },
            component_type: "Agent",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build flow", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks).toHaveLength(2);
    });
  });

  describe("isolation across messages", () => {
    it("should_not_carry_tasks_from_previous_message_into_a_new_one", async () => {
      // First send adds a component.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "ChatInput-abc" },
            component_type: "ChatInput",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "added", validated: true },
          });
        },
      );
      // Second send is unrelated — no flow_update events.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: { result: "ack", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("add it", TEST_MODEL);
      });
      await act(async () => {
        await result.current.handleSend("thanks", TEST_MODEL);
      });

      const assistantMsgs = result.current.messages.filter(
        (m) => m.role === "assistant",
      );
      expect(assistantMsgs[0]?.buildTasks).toHaveLength(1);
      expect(assistantMsgs[1]?.buildTasks ?? []).toEqual([]);
    });
  });

  describe("regression — flow proposal path does NOT add tasks", () => {
    it("should_not_emit_build_task_for_set_flow_event_since_that_is_a_destructive_proposal", async () => {
      // set_flow goes through the Continue/Dismiss gate, not the live
      // task list. Treating it as a task would surface "set flow" as a
      // single bullet that hides 10 components — the proposal card
      // already covers that case better.
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: { data: { nodes: [], edges: [] } },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build", TEST_MODEL);
      });

      const msg = result.current.messages.find((m) => m.role === "assistant");
      expect(msg?.buildTasks ?? []).toEqual([]);
    });
  });
});
