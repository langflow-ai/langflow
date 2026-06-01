/**
 * F1 — Frontend SSE handler for `file_written` events.
 *
 * When the agent writes a file via the sandboxed FS toolkit, the backend
 * streams a ``file_written`` SSE event. The chat hook must:
 *   1. Append a ``WrittenFile`` entry to the active assistant message.
 *   2. Preserve insertion order across multiple events.
 *   3. Keep every other field on the message intact (no clobbering of the
 *      progress / flowActions / content fields).
 *
 * The pattern follows the existing onFlowUpdate / onFlowPreview tests.
 */

import { act, renderHook } from "@testing-library/react";

import type { AgenticFileWrittenEvent } from "@/controllers/API/queries/agentic/types";
import { useAssistantChat } from "../use-assistant-chat";

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => {},
}));

// Capture the StreamCallbacks the hook passes in so we can drive them in tests.
let capturedCallbacks: any = null;
const mockPostAssistStream = jest.fn(async (_req: unknown, callbacks: any) => {
  capturedCallbacks = callbacks;
});
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
  const fn = (selector: (s: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
  return { __esModule: true, default: fn };
});

jest.mock("@/stores/flowStore", () => {
  const state = {
    setNodes: jest.fn(),
    setEdges: jest.fn(),
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

function makeFileWrittenEvent(
  overrides: Partial<AgenticFileWrittenEvent> = {},
): AgenticFileWrittenEvent {
  return {
    event: "file_written",
    action: "write_file",
    path: "DOCS.md",
    size: 100,
    ...overrides,
  };
}

describe("useAssistantChat — file_written handler (F1)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedCallbacks = null;
  });

  it("should append a WrittenFile entry to the assistant message when file_written arrives", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("crie um doc", TEST_MODEL);
    });

    // The hook calls postAssistStream synchronously and registers callbacks.
    expect(capturedCallbacks).not.toBeNull();
    expect(typeof capturedCallbacks.onFileWritten).toBe("function");

    // Drive the file_written event from the test.
    act(() => {
      capturedCallbacks.onFileWritten(makeFileWrittenEvent());
    });

    const messages = result.current.messages;
    const assistantMsg = messages.find((m) => m.role === "assistant");
    expect(assistantMsg).toBeDefined();
    expect(assistantMsg?.writtenFiles).toHaveLength(1);
    expect(assistantMsg?.writtenFiles?.[0]).toMatchObject({
      action: "write_file",
      path: "DOCS.md",
      size: 100,
    });
  });

  it("should preserve order when multiple file_written events arrive", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("crie docs", TEST_MODEL);
    });

    act(() => {
      capturedCallbacks.onFileWritten(makeFileWrittenEvent({ path: "A.md" }));
      capturedCallbacks.onFileWritten(makeFileWrittenEvent({ path: "B.md" }));
      capturedCallbacks.onFileWritten(
        makeFileWrittenEvent({ path: "A.md", action: "edit_file" }),
      );
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.writtenFiles?.map((f) => [f.action, f.path])).toEqual([
      ["write_file", "A.md"],
      ["write_file", "B.md"],
      ["edit_file", "A.md"],
    ]);
  });

  it("should keep other message fields intact when file_written arrives", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("crie doc", TEST_MODEL);
    });

    // Simulate a progress event before the file_written so we can check the
    // progress field is preserved.
    act(() => {
      capturedCallbacks.onProgress?.({
        event: "progress",
        step: "generating_document",
        attempt: 1,
        max_attempts: 4,
        message: "Generating document...",
      });
      capturedCallbacks.onFileWritten(makeFileWrittenEvent());
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.progress?.step).toBe("generating_document");
    expect(assistantMsg?.writtenFiles).toHaveLength(1);
  });
});
