/**
 * Tests for progress field propagation in useAssistantChat.
 *
 * Verifies that onProgress events correctly persist componentCode, error,
 * and className into the assistant message state — the intermediate
 * visibility feature.
 */

import { act, renderHook } from "@testing-library/react";
import { useAssistantChat } from "../use-assistant-chat";

// --- Mocks ---

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({
      mutateAsync: jest.fn(),
    }),
  }),
);

jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => jest.fn(),
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

describe("useAssistantChat — progress field propagation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPostAssistStream.mockResolvedValue(undefined);
  });

  describe("componentCode in progress", () => {
    it("should persist componentCode from validating progress event", async () => {
      const code = "class MyComponent(Component):\n    pass";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 0,
            max_attempts: 3,
            component_code: code,
            message: "Validating...",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.progress).toBeDefined();
      expect(assistantMsg.progress?.componentCode).toBe(code);
    });

    it("should persist componentCode from validation_failed progress event", async () => {
      const code = "class BrokenComp(Component):\n    pass";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validation_failed",
            attempt: 0,
            max_attempts: 3,
            component_code: code,
            error: "SyntaxError: invalid syntax",
            class_name: "BrokenComp",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.progress?.componentCode).toBe(code);
    });

    it("should not have componentCode when generating_component step has none", async () => {
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

      expect(
        result.current.messages[1].progress?.componentCode,
      ).toBeUndefined();
    });
  });

  describe("error in progress", () => {
    it("should persist error from validation_failed progress event", async () => {
      const errorMsg = "ModuleNotFoundError: No module named 'pandas'";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validation_failed",
            attempt: 0,
            max_attempts: 3,
            error: errorMsg,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      expect(result.current.messages[1].progress?.error).toBe(errorMsg);
    });

    it("should persist error from retrying progress event", async () => {
      const retryError =
        "AttributeError: type object has no attribute 'inputs'";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "retrying",
            attempt: 1,
            max_attempts: 3,
            error: retryError,
            message: "Retrying with error context...",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      expect(result.current.messages[1].progress?.error).toBe(retryError);
    });

    it("should not have error when step has no error", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 0,
            max_attempts: 3,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      expect(result.current.messages[1].progress?.error).toBeUndefined();
    });
  });

  describe("className in progress", () => {
    it("should persist className from validation_failed progress event", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validation_failed",
            attempt: 0,
            max_attempts: 3,
            class_name: "BrokenComp",
            error: "Some error",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      expect(result.current.messages[1].progress?.className).toBe("BrokenComp");
    });
  });

  describe("message field in progress", () => {
    it("should persist message from progress event", async () => {
      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 0,
            max_attempts: 3,
            message: "Validating component code...",
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      expect(result.current.messages[1].progress?.message).toBe(
        "Validating component code...",
      );
    });
  });

  describe("full progress lifecycle", () => {
    it("should update progress fields through the full validation lifecycle", async () => {
      const code = "class MyComp(Component):\n    pass";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          // Step 1: generating
          callbacks.onProgress({
            event: "progress",
            step: "generating_component",
            attempt: 0,
            max_attempts: 3,
            message: "Generating response...",
          });

          // Step 2: validating with code
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 0,
            max_attempts: 3,
            message: "Validating...",
            component_code: code,
          });

          // Step 3: validation failed with error + code
          callbacks.onProgress({
            event: "progress",
            step: "validation_failed",
            attempt: 0,
            max_attempts: 3,
            error: "Missing inputs",
            component_code: code,
            class_name: "MyComp",
          });

          // Step 4: retrying with error
          callbacks.onProgress({
            event: "progress",
            step: "retrying",
            attempt: 0,
            max_attempts: 3,
            error: "Missing inputs",
            message: "Retrying...",
          });

          // Complete
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "Fixed component",
              validated: true,
              class_name: "MyComp",
              component_code: code,
              validation_attempts: 2,
            },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      const assistantMsg = result.current.messages[1];
      // After complete, progress should have the last progress state (retrying)
      // But status should be "complete" with the result
      expect(assistantMsg.status).toBe("complete");
      expect(assistantMsg.result?.validated).toBe(true);
      expect(assistantMsg.result?.componentCode).toBe(code);
      expect(assistantMsg.result?.className).toBe("MyComp");
    });

    it("should reflect the latest progress event fields", async () => {
      const code1 = "class V1(Component): pass";
      const code2 = "class V2(Component): pass";

      mockPostAssistStream.mockImplementation(
        async (_request: unknown, callbacks: Record<string, Function>) => {
          // First: validating with code1
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 0,
            max_attempts: 3,
            component_code: code1,
          });

          // Then: validation_failed with code1 and error
          callbacks.onProgress({
            event: "progress",
            step: "validation_failed",
            attempt: 0,
            max_attempts: 3,
            component_code: code1,
            error: "Bad code",
          });

          // After retry: validating with code2 (new generated code)
          callbacks.onProgress({
            event: "progress",
            step: "validating",
            attempt: 1,
            max_attempts: 3,
            component_code: code2,
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("create a component", TEST_MODEL);
      });

      const progress = result.current.messages[1].progress;
      // Should reflect the LATEST progress event
      expect(progress?.step).toBe("validating");
      expect(progress?.componentCode).toBe(code2);
      expect(progress?.attempt).toBe(1);
      // Error from the previous step should be replaced (undefined in validating)
      expect(progress?.error).toBeUndefined();
    });
  });
});
