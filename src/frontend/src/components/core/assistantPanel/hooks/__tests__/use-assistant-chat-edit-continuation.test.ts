import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * Edit-approval continuation ("execution stack" for the Agent).
 *
 * When the user asks the assistant to BOTH edit the flow AND run it, the
 * agent proposes the edit through a man-in-the-loop diff card and stops.
 * Approving the card only mutates the React Flow store — the backend reads
 * the working flow from the DB by flow_id, so the run must happen in a
 * follow-up turn AFTER the canvas is persisted.
 *
 * Contract: once every flow action on a message leaves "pending" and at
 * least one was "applied", the hook persists the canvas (saveFlow) and
 * fires ONE silent/internal continuation turn so the agent resumes the
 * rest of the original request (e.g. running the flow). Mirrors the
 * existing plan-gate continuation. A dismiss-only resolution must NOT
 * continue (the change the user wanted was rejected).
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

const mockSaveFlow = jest.fn();
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
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

async function flushTimers() {
  await act(async () => {
    jest.runOnlyPendingTimers();
    await Promise.resolve();
  });
}

/** Drive one assistant turn that proposes `n` field edits, then ends.
 * `continuationExpected` mirrors the backend flag: true when a deferred
 * step (e.g. run) was requested alongside the edit. */
function mockTurnWithEdits(n: number, continuationExpected = true) {
  mockPostAssistStream.mockImplementationOnce(
    async (_req: unknown, callbacks: Record<string, Function>) => {
      for (let i = 1; i <= n; i++) {
        callbacks.onFlowUpdate({
          event: "flow_update",
          action: "edit_field",
          id: `act-${i}`,
          component_id: "ChatInput-1",
          component_type: "ChatInput",
          field: "input_value",
          old_value: "crocodile",
          new_value: "Cat",
          description: "Set input_value to 'Cat' on ChatInput",
          patch: [
            {
              op: "replace",
              path: "/data/nodes/0/data/node/template/input_value/value",
              value: "Cat",
            },
          ],
        });
      }
      callbacks.onComplete({
        event: "complete",
        data: {
          result: "Proposed the edit.",
          validated: true,
          continuation_expected: continuationExpected,
        },
      });
    },
  );
  mockPostAssistStream.mockResolvedValue(undefined);
}

async function proposeEditsTurn(n: number, continuationExpected = true) {
  mockTurnWithEdits(n, continuationExpected);
  const hook = renderHook(() => useAssistantChat());
  await act(async () => {
    await hook.result.current.handleSend(
      continuationExpected
        ? "change the chat input to Cat and run the flow"
        : "improve the agent instructions",
      TEST_MODEL,
    );
  });
  await flushTimers();
  return hook;
}

function assistantMsgId(result: {
  current: { messages: { id: string; role: string }[] };
}) {
  return result.current.messages.find((m) => m.role === "assistant")!.id;
}

describe("useAssistantChat — edit-approval continuation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    mockPostAssistStream.mockResolvedValue(undefined);
    mockSaveFlow.mockResolvedValue(undefined);
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("should_persist_canvas_then_send_a_silent_continuation_turn_when_an_edit_is_applied", async () => {
    const { result } = await proposeEditsTurn(1);
    const msgId = assistantMsgId(result);

    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "applied");
    });
    await flushTimers();

    // Canvas persisted BEFORE the continuation so the backend (which reads
    // the working flow from the DB by flow_id) sees the applied edit.
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);

    // Exactly one continuation turn, carrying the continuation signal.
    expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
    const continuationInput = mockPostAssistStream.mock.calls[1][0]
      .input_value as string;
    expect(continuationInput.toLowerCase()).toContain("applied");
    expect(continuationInput.toLowerCase()).toContain("continue");

    // The continuation signal is a backend protocol string, never shown as
    // a user-authored bubble.
    const userContents = result.current.messages
      .filter((m) => m.role === "user")
      .map((m) => m.content);
    expect(userContents).toEqual([
      "change the chat input to Cat and run the flow",
    ]);
  });

  // Regression guard for reference_assistant_edit_continuation: the
  // continuation turn MUST NOT fire until saveFlow has fully resolved,
  // even when persistence is slow (real PATCH network). If a future
  // refactor drops the `await` before handleSend, the backend would read
  // the pre-edit flow. (saveFlow is async → ordering holds today; this
  // pins it permanently.)
  it("should_not_fire_continuation_until_a_slow_saveFlow_resolves", async () => {
    let releaseSave: () => void = () => {};
    mockSaveFlow.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          releaseSave = resolve;
        }),
    );

    const { result } = await proposeEditsTurn(1);
    const msgId = assistantMsgId(result);
    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);

    let actionPromise: Promise<void>;
    act(() => {
      actionPromise = result.current.handleUpdateFlowAction(
        msgId,
        "act-1",
        "applied",
      );
    });
    await flushTimers();

    // saveFlow is in-flight → the continuation must NOT have been sent.
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);

    // Persistence completes → exactly now the continuation may fire.
    await act(async () => {
      releaseSave();
      await actionPromise;
    });
    await flushTimers();

    expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
  });

  it("should_NOT_continue_for_a_pure_edit_when_no_step_was_deferred", async () => {
    // Production glitch: "improve the agent instructions" (no run/test)
    // approved → a redundant 2nd assistant message appeared. With
    // continuation_expected=false the approval must NOT fire a continuation.
    const { result } = await proposeEditsTurn(1, false);
    const msgId = assistantMsgId(result);

    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "applied");
    });
    await flushTimers();

    expect(mockSaveFlow).not.toHaveBeenCalled();
    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
  });

  it("should_NOT_continue_when_the_only_action_is_dismissed", async () => {
    const { result } = await proposeEditsTurn(1);
    const msgId = assistantMsgId(result);

    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "dismissed");
    });
    await flushTimers();

    expect(mockSaveFlow).not.toHaveBeenCalled();
    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
  });

  it("should_continue_only_once_after_the_LAST_pending_action_resolves", async () => {
    const { result } = await proposeEditsTurn(2);
    const msgId = assistantMsgId(result);

    // First edit applied, second still pending → no continuation yet.
    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "applied");
    });
    await flushTimers();
    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
    expect(mockSaveFlow).not.toHaveBeenCalled();

    // Second resolved → exactly one continuation fires.
    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-2", "applied");
    });
    await flushTimers();
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
  });

  it("should_not_fire_a_second_continuation_if_an_action_is_re_updated", async () => {
    const { result } = await proposeEditsTurn(1);
    const msgId = assistantMsgId(result);

    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "applied");
    });
    await flushTimers();
    expect(mockPostAssistStream).toHaveBeenCalledTimes(2);

    // Re-updating the same (already resolved) action must not re-trigger.
    await act(async () => {
      await result.current.handleUpdateFlowAction(msgId, "act-1", "applied");
    });
    await flushTimers();
    expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
  });
});
