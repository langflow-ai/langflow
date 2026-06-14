import { act, renderHook } from "@testing-library/react";
import { useAssistantChat } from "../use-assistant-chat";

// --- Mocks ---

// useUpdateNodeInternals requires a ReactFlow provider at runtime. The hook
// is only used to refresh handle positions after the assistant mutates a
// node, which is irrelevant in pure-logic tests for the chat hook.
jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => {},
}));

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

const mockValidateComponent = jest.fn();
jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({
      mutateAsync: mockValidateComponent,
    }),
  }),
);

const mockAddComponent = jest.fn();
jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => mockAddComponent,
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

// useFlowStore is invoked via getState() inside applyFlowUpdate. The hook
// calls setNodes/setEdges as the side effect we assert against — we expose
// jest.fn() spies so tests can verify whether the canvas was mutated.
const mockSetNodes = jest.fn();
const mockSetEdges = jest.fn();
const mockPaste = jest.fn();
let _mockNodes: unknown[] = [];
let _mockEdges: unknown[] = [];
const mockGetNodes = jest.fn(() => _mockNodes);
const mockGetEdges = jest.fn(() => _mockEdges);
jest.mock("@/stores/flowStore", () => {
  const state = {
    setNodes: (...args: unknown[]) => mockSetNodes(...args),
    setEdges: (...args: unknown[]) => mockSetEdges(...args),
    paste: (...args: unknown[]) => mockPaste(...args),
    get nodes() {
      return mockGetNodes();
    },
    get edges() {
      return mockGetEdges();
    },
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

describe("useAssistantChat", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPostAssistStream.mockResolvedValue(undefined);
  });

  describe("initial state", () => {
    it("should start with empty messages, not processing, no current step", () => {
      const { result } = renderHook(() => useAssistantChat());

      expect(result.current.messages).toEqual([]);
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.currentStep).toBeNull();
    });
  });

  describe("handleSend", () => {
    it("should not send when isProcessing is true", async () => {
      // Make postAssistStream hang to keep isProcessing=true
      mockPostAssistStream.mockImplementation(() => new Promise(() => {}));

      const { result } = renderHook(() => useAssistantChat());

      // First call starts processing
      act(() => {
        result.current.handleSend("first message", TEST_MODEL);
      });

      // Second call should be ignored
      await act(async () => {
        await result.current.handleSend("second message", TEST_MODEL);
      });

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
    });

    // Bug: handleSend created a fresh AbortController without aborting the
    // previous one. internal:true (skip-all bridge / edit-continuation)
    // bypasses the isProcessing guard, so two SSE pumps run concurrently
    // and the first reader is leaked.
    it("should abort the previous in-flight stream when a new send starts", async () => {
      // First stream stays in-flight (never resolves); the chained second
      // send resolves so the test doesn't hang.
      mockPostAssistStream.mockImplementationOnce(() => new Promise(() => {}));

      const { result } = renderHook(() => useAssistantChat());

      act(() => {
        result.current.handleSend("first message", TEST_MODEL);
      });
      const firstSignal = mockPostAssistStream.mock.calls[0][2] as AbortSignal;
      expect(firstSignal.aborted).toBe(false);

      await act(async () => {
        await result.current.handleSend("second message", TEST_MODEL, {
          internal: true,
        });
      });

      expect(firstSignal.aborted).toBe(true);
    });

    it("should not send when model provider is null", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", {
          ...TEST_MODEL,
          provider: "",
        });
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });

    it("should not send when model name is null", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", {
          ...TEST_MODEL,
          name: "",
        });
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });

    it("should not send when model is null", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", null);
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });

    it("should call postAssistStream with correct parameters", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build a component", TEST_MODEL);
      });

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
      const [request, , signal] = mockPostAssistStream.mock.calls[0];

      expect(request).toMatchObject({
        flow_id: "test-flow-id",
        input_value: "build a component",
        provider: "openai",
        model_name: "gpt-4",
      });
      expect(request.session_id).toBeDefined();
      expect(signal).toBeInstanceOf(AbortSignal);
    });

    it("should add user and assistant messages on send", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", TEST_MODEL);
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].role).toBe("user");
      expect(result.current.messages[0].content).toBe("hello");
      expect(result.current.messages[0].status).toBe("complete");
      expect(result.current.messages[1].role).toBe("assistant");
      expect(result.current.messages[1].status).toBe("streaming");
    });

    it("should update currentStep on progress callback", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "generating_component",
            attempt: 0,
            max_attempts: 3,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      // currentStep is set to null on completion via catch/finally, but the
      // progress event itself sets it
      // Since mockPostAssistStream finishes (no onComplete called),
      // isProcessing stays true via the catch path
      expect(result.current.messages[1].progress).toBeDefined();
      expect(result.current.messages[1].progress?.step).toBe(
        "generating_component",
      );
    });

    it("should accumulate content on token callback", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onToken({ event: "token", chunk: "Hello " });
          callbacks.onToken({ event: "token", chunk: "world!" });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("question", TEST_MODEL);
      });

      expect(result.current.messages[1].content).toBe("Hello world!");
    });

    it("should finalize message on complete callback", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "Here is your component",
              validated: true,
              class_name: "MyComponent",
              component_code: "class MyComponent(Component): ...",
              validation_attempts: 1,
            },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.status).toBe("complete");
      expect(assistantMsg.content).toBe("Here is your component");
      expect(assistantMsg.result?.validated).toBe(true);
      expect(assistantMsg.result?.className).toBe("MyComponent");
      expect(assistantMsg.result?.componentCode).toBe(
        "class MyComponent(Component): ...",
      );
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.currentStep).toBeNull();
    });

    it("should_propagate_usage_and_duration_from_complete_event", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "done",
              validated: true,
              usage: {
                input_tokens: 110,
                output_tokens: 54,
                total_tokens: 164,
              },
              duration_seconds: 1.234,
            },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hi", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.usage).toEqual({
        input_tokens: 110,
        output_tokens: 54,
        total_tokens: 164,
      });
      // Duration is stored in milliseconds to match the playground's
      // MessageMetadata renderer (which formats seconds from a ms input).
      expect(assistantMsg.duration).toBe(1234);
    });

    it("should_leave_usage_and_duration_undefined_when_complete_event_omits_them", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: { result: "done", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hi", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.usage).toBeUndefined();
      expect(assistantMsg.duration).toBeUndefined();
    });

    it("should_keep_existing_complete_fields_alongside_usage_and_duration", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "hello",
              validated: true,
              class_name: "X",
              usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
              duration_seconds: 0.5,
            },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hi", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      // Existing finalize-message behavior is preserved.
      expect(assistantMsg.status).toBe("complete");
      expect(assistantMsg.content).toBe("hello");
      expect(assistantMsg.result?.className).toBe("X");
      // New fields land alongside the existing ones.
      expect(assistantMsg.usage?.total_tokens).toBe(2);
      expect(assistantMsg.duration).toBe(500);
    });

    it("should set error status on error callback", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onError({
            event: "error",
            message: "API key invalid",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("test", TEST_MODEL);
      });

      expect(result.current.messages[1].status).toBe("error");
      expect(result.current.messages[1].error).toBe("API key invalid");
      expect(result.current.isProcessing).toBe(false);
    });

    it("should set cancelled status on cancelled callback", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onCancelled({
            event: "cancelled",
            message: "User cancelled",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("test", TEST_MODEL);
      });

      expect(result.current.messages[1].status).toBe("cancelled");
      expect(result.current.isProcessing).toBe(false);
    });

    it("should set error status on network error (non-AbortError)", async () => {
      mockPostAssistStream.mockRejectedValue(new Error("Network failure"));

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("test", TEST_MODEL);
      });

      expect(result.current.messages[1].status).toBe("error");
      expect(result.current.messages[1].error).toBe(
        "Failed to connect to assistant",
      );
      expect(result.current.isProcessing).toBe(false);
    });

    it("should not set error on AbortError", async () => {
      const abortError = new Error("Aborted");
      abortError.name = "AbortError";
      mockPostAssistStream.mockRejectedValue(abortError);

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("test", TEST_MODEL);
      });

      // Message should remain streaming (not error)
      expect(result.current.messages[1].status).toBe("streaming");
      expect(result.current.isProcessing).toBe(false);
    });
  });

  describe("handleApprove", () => {
    it("should validate and add component for a validated message", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "component",
              validated: true,
              class_name: "TestComp",
              component_code: "class TestComp(Component): pass",
            },
          });
        },
      );

      mockValidateComponent.mockResolvedValue({
        data: { display_name: "TestComp" },
        type: "TestComp",
      });

      const { result } = renderHook(() => useAssistantChat());

      // Send a message first to get a message with componentCode
      await act(async () => {
        await result.current.handleSend("create", TEST_MODEL);
      });

      const messageId = result.current.messages[1].id;

      await act(async () => {
        await result.current.handleApprove(messageId);
      });

      expect(mockValidateComponent).toHaveBeenCalledWith({
        code: "class TestComp(Component): pass",
        frontend_node: {},
      });
      expect(mockAddComponent).toHaveBeenCalledWith(
        { display_name: "TestComp" },
        "TestComp",
      );
    });

    it("should skip when message has no componentCode", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: { result: "just text", validated: false },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("question", TEST_MODEL);
      });

      const messageId = result.current.messages[1].id;

      await act(async () => {
        await result.current.handleApprove(messageId);
      });

      expect(mockValidateComponent).not.toHaveBeenCalled();
    });

    it("should log error when validation fails", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "component",
              validated: true,
              component_code: "bad code",
            },
          });
        },
      );

      mockValidateComponent.mockRejectedValue(new Error("Validation error"));
      const consoleSpy = jest.spyOn(console, "error").mockImplementation();

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create", TEST_MODEL);
      });

      const messageId = result.current.messages[1].id;

      await act(async () => {
        await result.current.handleApprove(messageId);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to validate or add component to canvas:",
        expect.any(Error),
      );

      consoleSpy.mockRestore();
    });
  });

  describe("plan proposal flow (BUILD-mode planning gate)", () => {
    it("should_record_pending_plan_proposal_when_onFlowUpdate_receives_propose_plan", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "## Plan\n\nBuild a chatbot.",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build me a chatbot", TEST_MODEL);
      });

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );
      expect(assistantMsg?.pendingPlanProposal?.markdown).toBe(
        "## Plan\n\nBuild a chatbot.",
      );
      expect(assistantMsg?.planProposalStatus).toBe("pending");
    });

    it("should_not_mutate_canvas_when_propose_plan_event_arrives", async () => {
      // Plan events are purely advisory — they must NOT touch the canvas.
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });

      expect(mockSetNodes).not.toHaveBeenCalled();
      expect(mockSetEdges).not.toHaveBeenCalled();
    });

    it("should_mark_plan_as_approved_when_handleApprovePlan_called", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );
      expect(assistantMsg).toBeDefined();

      mockPostAssistStream.mockReset();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await result.current.handleApprovePlan(assistantMsg!.id);
      });

      const updated = result.current.messages.find(
        (m) => m.id === assistantMsg!.id,
      );
      expect(updated?.planProposalStatus).toBe("approved");
    });

    it("should_send_approval_turn_to_backend_when_handleApprovePlan_called", async () => {
      // Approval must reach the backend as a normal user turn so the agent
      // resumes — the backend has no state about "this plan was approved",
      // it just sees the next user message and the prompt tells it what to do.
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan",
          });
          // Fire onComplete so isProcessing resets — otherwise the next
          // handleSend would short-circuit on the "already processing" guard.
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );

      mockPostAssistStream.mockReset();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await result.current.handleApprovePlan(assistantMsg!.id);
      });

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
      const [request] = mockPostAssistStream.mock.calls[0];
      expect(request.input_value.toLowerCase()).toContain("approve");
    });

    it("should_mark_plan_as_refining_when_handleDismissPlan_called", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );
      mockPostAssistStream.mockReset();

      act(() => {
        result.current.handleDismissPlan(assistantMsg!.id);
      });

      const updated = result.current.messages.find(
        (m) => m.id === assistantMsg!.id,
      );
      // Dismiss no longer terminates the planning gate — it transitions to
      // "refining" so the next user message can carry the dismissed plan
      // as context (see use-assistant-chat-plan-refining.test.ts).
      expect(updated?.planProposalStatus).toBe("refining");
      // Dismiss does NOT send a new turn — the user types refinement
      // feedback as a regular message.
      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });
  });

  describe("handleStopGeneration", () => {
    it("should cancel streaming and reset state", async () => {
      // Make postAssistStream hang to simulate in-progress
      mockPostAssistStream.mockImplementation(() => new Promise(() => {}));

      const { result } = renderHook(() => useAssistantChat());

      act(() => {
        result.current.handleSend("test", TEST_MODEL);
      });

      // Wait for messages to be set
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      act(() => {
        result.current.handleStopGeneration();
      });

      expect(result.current.isProcessing).toBe(false);
      expect(result.current.currentStep).toBeNull();

      const streamingMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );
      expect(streamingMsg?.status).toBe("cancelled");
    });
  });

  describe("handleClearHistory", () => {
    it("should clear all messages and reset state", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", TEST_MODEL);
      });

      expect(result.current.messages.length).toBeGreaterThan(0);

      act(() => {
        result.current.handleClearHistory();
      });

      expect(result.current.messages).toEqual([]);
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.currentStep).toBeNull();
    });
  });

  describe("bugs and edge cases", () => {
    it("completedSteps should track step transitions", async () => {
      const progressSteps: string[] = [];

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "generating",
            attempt: 1,
            max_attempts: 3,
          });
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 1,
            max_attempts: 3,
          });
          callbacks.onProgress({
            event: "progress",
            step: "validated",
            attempt: 1,
            max_attempts: 3,
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "done", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      // completedSteps should contain the previous steps
      expect(assistantMsg.completedSteps).toBeDefined();
      expect(assistantMsg.completedSteps!.length).toBeGreaterThan(0);
    });

    it("completedSteps should contain the previous step when a new step arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "generating",
            attempt: 1,
            max_attempts: 3,
          });
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 1,
            max_attempts: 3,
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "done", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      // When "validating" arrives, "generating" should be in completedSteps
      expect(assistantMsg.completedSteps).toContain("generating");
    });

    it("should use same session_id across multiple sends", async () => {
      // Must call onComplete so isProcessing resets to false between sends
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onComplete({
            event: "complete",
            data: { result: "done", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("first", TEST_MODEL);
      });
      const firstSessionId = mockPostAssistStream.mock.calls[0][0].session_id;

      await act(async () => {
        await result.current.handleSend("second", TEST_MODEL);
      });
      const secondSessionId = mockPostAssistStream.mock.calls[1][0].session_id;

      expect(firstSessionId).toBe(secondSessionId);
    });

    it("should get new session_id after clearHistory", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("before clear", TEST_MODEL);
      });
      const sessionBefore = mockPostAssistStream.mock.calls[0][0].session_id;

      act(() => {
        result.current.handleClearHistory();
      });

      await act(async () => {
        await result.current.handleSend("after clear", TEST_MODEL);
      });
      const sessionAfter = mockPostAssistStream.mock.calls[1][0].session_id;

      expect(sessionBefore).not.toBe(sessionAfter);
    });

    it("should_prefix_session_id_with_agentic_to_isolate_from_playground", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("hello", TEST_MODEL);
      });

      const sessionId = mockPostAssistStream.mock.calls[0][0].session_id;
      expect(sessionId).toMatch(/^agentic_/);
    });

    it("should_prefix_session_id_with_agentic_after_clear_history", async () => {
      const { result } = renderHook(() => useAssistantChat());

      act(() => {
        result.current.handleClearHistory();
      });

      await act(async () => {
        await result.current.handleSend("after clear", TEST_MODEL);
      });

      const sessionId = mockPostAssistStream.mock.calls[0][0].session_id;
      expect(sessionId).toMatch(/^agentic_/);
    });
  });

  describe("flow proposal add-vs-replace mode", () => {
    const FRESH_FLOW = {
      name: "Fresh",
      data: {
        nodes: [
          { id: "ChatInput-new", position: { x: 0, y: 0 } },
          { id: "Agent-new", position: { x: 200, y: 0 } },
        ],
        edges: [{ id: "e1", source: "ChatInput-new", target: "Agent-new" }],
      },
    };

    beforeEach(() => {
      _mockNodes = [];
      _mockEdges = [];
    });

    it("should_replace_canvas_when_mode_is_replace", async () => {
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: FRESH_FLOW,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });
      const msg = result.current.messages[1];

      mockSetNodes.mockClear();

      act(() => {
        result.current.handleApplyFlowProposal(msg.id, "replace");
      });

      // Replace path: setNodes called with a plain array equal to the
      // proposal's nodes (no merge logic, just overwrite).
      expect(mockSetNodes).toHaveBeenCalled();
      const firstCallArg = mockSetNodes.mock.calls[0][0];
      expect(Array.isArray(firstCallArg)).toBe(true);
      expect((firstCallArg as Array<{ id: string }>).map((n) => n.id)).toEqual(
        FRESH_FLOW.data.nodes.map((n) => n.id),
      );
    });

    it("should_default_to_replace_when_mode_arg_is_omitted", async () => {
      // Backwards compatibility: existing callers without the second
      // arg keep the destructive semantic.
      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: FRESH_FLOW,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });
      const msg = result.current.messages[1];

      mockSetNodes.mockClear();

      act(() => {
        result.current.handleApplyFlowProposal(msg.id);
      });

      const firstCallArg = mockSetNodes.mock.calls[0][0];
      expect(Array.isArray(firstCallArg)).toBe(true);
    });

    it("should_merge_into_existing_canvas_when_mode_is_add", async () => {
      // Plant existing canvas state via the mock store getters.
      _mockNodes = [{ id: "Existing-1", position: { x: 0, y: 0 } }];
      _mockEdges = [];

      mockPostAssistStream.mockImplementation(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: FRESH_FLOW,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });
      const msg = result.current.messages[1];

      mockSetNodes.mockClear();
      mockSetEdges.mockClear();

      act(() => {
        result.current.handleApplyFlowProposal(msg.id, "add");
      });

      // Merge path: setNodes called with a plain array equal to the
      // concatenation of existing + proposal (with offset/remap applied
      // by the helper). Length must be existing.length + proposal.length.
      expect(mockSetNodes).toHaveBeenCalled();
      const arg = mockSetNodes.mock.calls[0][0] as Array<{ id: string }>;
      expect(Array.isArray(arg)).toBe(true);
      expect(arg).toHaveLength(1 + FRESH_FLOW.data.nodes.length);
      expect(arg[0].id).toBe("Existing-1");
    });
  });

  describe("flow proposal gating (set_flow only)", () => {
    const SAMPLE_FLOW = {
      name: "Test Flow",
      data: {
        nodes: [{ id: "n1" }, { id: "n2" }, { id: "n3" }],
        edges: [{ id: "e1", source: "n1", target: "n2" }],
      },
    };

    it("should_buffer_set_flow_into_pendingFlowProposal_when_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build me a chatbot", TEST_MODEL);
      });

      const msg = result.current.messages[1];
      expect(msg.pendingFlowProposal).toBeDefined();
      expect(msg.pendingFlowProposal?.nodeCount).toBe(3);
      expect(msg.pendingFlowProposal?.edgeCount).toBe(1);
      expect(msg.flowProposalStatus).toBe("pending");
    });

    it("should_NOT_mutate_canvas_when_set_flow_event_arrives", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build a flow", TEST_MODEL);
      });

      expect(mockSetNodes).not.toHaveBeenCalled();
      expect(mockSetEdges).not.toHaveBeenCalled();
    });

    it("should_apply_add_component_live_to_canvas_without_buffering", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "new-node" },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("add chatinput", TEST_MODEL);
      });

      // Live apply: setNodes was called for the incremental edit
      expect(mockSetNodes).toHaveBeenCalled();
      // No proposal buffered for incremental edits
      const msg = result.current.messages[1];
      expect(msg.pendingFlowProposal).toBeUndefined();
      expect(msg.flowProposalStatus).toBeUndefined();
    });

    it("should_apply_configure_live_to_canvas_without_buffering", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "configure",
            component_id: "Agent-x",
            params: { temperature: 0.5 },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("set temperature", TEST_MODEL);
      });

      expect(mockSetNodes).toHaveBeenCalled();
      const msg = result.current.messages[1];
      expect(msg.pendingFlowProposal).toBeUndefined();
    });

    it("should_route_edit_field_to_flowActions_carousel_not_proposal", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "edit_field",
            id: "edit-1",
            component_id: "OpenAIModel-y",
            component_type: "OpenAIModel",
            field: "model_name",
            old_value: "gpt-3.5",
            new_value: "gpt-4o",
            description: "Switch model",
            patch: [],
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("change model", TEST_MODEL);
      });

      const msg = result.current.messages[1];
      expect(msg.flowActions).toHaveLength(1);
      expect(msg.flowActions?.[0].type).toBe("edit_field");
      // Edit field is NOT a flow proposal
      expect(msg.pendingFlowProposal).toBeUndefined();
      // And does NOT touch canvas directly (FlowEditCarousel applies on accept)
      expect(mockSetNodes).not.toHaveBeenCalled();
    });

    it("should_apply_pendingFlowProposal_to_canvas_when_handleApplyFlowProposal_called", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "Flow built", validated: true, has_flow: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build chatbot", TEST_MODEL);
      });

      const messageId = result.current.messages[1].id;
      expect(mockSetNodes).not.toHaveBeenCalled();

      await act(async () => {
        result.current.handleApplyFlowProposal(messageId);
      });

      expect(mockSetNodes).toHaveBeenCalled();
      expect(mockSetEdges).toHaveBeenCalled();
      const msg = result.current.messages.find((m) => m.id === messageId);
      expect(msg?.flowProposalStatus).toBe("applied");
      // Spec: keep ``pendingFlowProposal`` on the message so the preview
      // card can render the muted "applied" state — matches the component
      // result card that stays visible after Add to Canvas.
      expect(msg?.pendingFlowProposal).toBeDefined();
    });

    it("should_keep_pendingFlowProposal_without_touching_canvas_when_dismissed", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "Flow built", validated: true, has_flow: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build chatbot", TEST_MODEL);
      });

      const messageId = result.current.messages[1].id;

      act(() => {
        result.current.handleDismissFlowProposal(messageId);
      });

      expect(mockSetNodes).not.toHaveBeenCalled();
      expect(mockSetEdges).not.toHaveBeenCalled();
      const msg = result.current.messages.find((m) => m.id === messageId);
      expect(msg?.flowProposalStatus).toBe("dismissed");
      // Spec: keep ``pendingFlowProposal`` so the muted "Dismissed" card
      // continues to render — disappearing the card erases the visual
      // record of what the user refused.
      expect(msg?.pendingFlowProposal).toBeDefined();
    });

    it("should_buffer_tail_edits_after_set_flow_into_proposal", async () => {
      // Defensive: agent prompt forbids this case, but if it happens we
      // don't want half the changes on canvas and half in a proposal.
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
          });
          // Tail edit AFTER set_flow — must also defer
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "configure",
            component_id: "Agent-x",
            params: { temperature: 0.7 },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("build with config", TEST_MODEL);
      });

      // No live writes — the tail configure was buffered too
      expect(mockSetNodes).not.toHaveBeenCalled();
      const msg = result.current.messages[1];
      expect(msg.flowProposalStatus).toBe("pending");
    });

    it("should_not_emit_proposal_when_only_incremental_edits_arrive", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "add_component",
            node: { id: "n1" },
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "connect",
            edge: { id: "e1", source: "a", target: "b" },
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "configure",
            component_id: "n1",
            params: { x: 1 },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("edit flow", TEST_MODEL);
      });

      expect(mockSetNodes).toHaveBeenCalled();
      expect(mockSetEdges).toHaveBeenCalled();
      const msg = result.current.messages[1];
      expect(msg.pendingFlowProposal).toBeUndefined();
      expect(msg.flowProposalStatus).toBeUndefined();
    });

    // Regression test for PR #12575 round 2 — proposal-mode build:
    // backend emits ``flow_update set_flow`` (no auto_apply) followed by
    // a ``progress flow_proposal_ready`` step and a terminal ``complete``
    // with ``has_flow=true``. The hook must keep ``pendingFlowProposal``
    // + ``flowProposalStatus="pending"`` on the message after the full
    // sequence drains so the AssistantFlowPreview card actually renders.
    // The earlier test ``should_buffer_set_flow_into_pendingFlowProposal``
    // only fired ``set_flow`` in isolation and missed the clobber that
    // can happen when ``onComplete`` overwrites the message AFTER the
    // proposal fields were set.
    it("should_keep_pendingFlowProposal_after_full_proposal_sequence_drains", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "generating_flow",
            attempt: 1,
            max_attempts: 4,
            message: "Working on the flow...",
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: SAMPLE_FLOW,
            // Note: NO auto_apply — single-ask proposal-mode build.
          });
          callbacks.onProgress({
            event: "progress",
            step: "flow_proposal_ready",
            attempt: 1,
            max_attempts: 4,
            message: "Flow ready — review and continue",
          });
          callbacks.onComplete({
            event: "complete",
            data: {
              result:
                "Built a Chat Flow: ChatInput → OpenAIModel → ChatOutput.",
              success: true,
              has_flow: true,
              continuation_expected: false,
            },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend(
          "Build a chat flow with ChatInput → OpenAI → ChatOutput",
          TEST_MODEL,
        );
      });

      const msg = result.current.messages[1];
      expect(msg.flowProposalStatus).toBe("pending");
      expect(msg.pendingFlowProposal).toBeDefined();
      expect(msg.pendingFlowProposal?.nodeCount).toBe(3);
      expect(msg.pendingFlowProposal?.edgeCount).toBe(1);
      // Canvas must remain untouched — the whole point of the gate.
      expect(mockSetNodes).not.toHaveBeenCalled();
      expect(mockSetEdges).not.toHaveBeenCalled();
    });
  });
});
