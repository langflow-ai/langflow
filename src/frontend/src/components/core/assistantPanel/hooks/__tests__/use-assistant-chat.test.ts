import { act, renderHook } from "@testing-library/react";
import { useAssistantChat } from "../use-assistant-chat";

// --- Mocks ---

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

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
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
});
