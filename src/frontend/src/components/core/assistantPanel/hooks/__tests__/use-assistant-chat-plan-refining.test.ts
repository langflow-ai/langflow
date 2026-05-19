import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * Refining-plan UX tests for `useAssistantChat`.
 *
 * Dismiss on a plan card no longer terminates the planning gate. Instead it
 * transitions the message into a "refining" state: the prior plan markdown is
 * stashed locally and re-injected into the user's next message so the agent
 * (which has no server-side conversation history) replans with full context.
 *
 * These tests drive the behavior end-to-end through the hook's public surface.
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

function emitPlan(markdown: string) {
  mockPostAssistStream.mockImplementationOnce(
    async (_request: unknown, callbacks: Record<string, Function>) => {
      callbacks.onFlowUpdate({
        event: "flow_update",
        action: "propose_plan",
        markdown,
      });
      callbacks.onComplete({
        event: "complete",
        data: { result: "", validated: true },
      });
    },
  );
}

async function setupWithPlan(markdown: string) {
  emitPlan(markdown);
  const hook = renderHook(() => useAssistantChat());
  await act(async () => {
    await hook.result.current.handleSend("build a chatbot", TEST_MODEL);
  });
  const assistantMsg = hook.result.current.messages.find(
    (m) => m.role === "assistant",
  )!;
  return { hook, assistantMsg };
}

describe("useAssistantChat — refining plan UX", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPostAssistStream.mockResolvedValue(undefined);
  });

  describe("handleDismissPlan transitions to refining", () => {
    it("should_set_planProposalStatus_to_refining_when_handleDismissPlan_called", async () => {
      const { hook, assistantMsg } = await setupWithPlan("## Plan body");

      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      const updated = hook.result.current.messages.find(
        (m) => m.id === assistantMsg.id,
      );
      expect(updated?.planProposalStatus).toBe("refining");
    });

    it("should_keep_markdown_on_message_so_card_stays_visible_after_dismiss", async () => {
      const { hook, assistantMsg } = await setupWithPlan("## Plan body");

      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      const updated = hook.result.current.messages.find(
        (m) => m.id === assistantMsg.id,
      );
      // The markdown must remain — the card relies on it to render the
      // refining-state view (no fetch, no re-emit).
      expect(updated?.pendingPlanProposal?.markdown).toBe("## Plan body");
    });

    it("should_not_send_a_new_backend_turn_when_handleDismissPlan_called", async () => {
      // Refining is user-driven: the user types feedback as a normal turn.
      // The hook must NOT auto-send anything on Dismiss.
      const { hook, assistantMsg } = await setupWithPlan("## Plan body");
      mockPostAssistStream.mockClear();

      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });
  });

  describe("handleSend prepends stashed plan when refining", () => {
    it("should_prepend_dismissed_plan_markdown_to_next_input_value_when_refining", async () => {
      const { hook, assistantMsg } = await setupWithPlan(
        "## Original plan\n\nUse OpenAI.",
      );
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await hook.result.current.handleSend("use Claude instead", TEST_MODEL);
      });

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
      const [request] = mockPostAssistStream.mock.calls[0];
      // The agent must see the prior plan AND the user's refinement.
      expect(request.input_value).toContain("## Original plan");
      expect(request.input_value).toContain("Use OpenAI.");
      expect(request.input_value).toContain("use Claude instead");
    });

    it("should_wrap_stashed_plan_in_a_clear_delimiter_so_the_llm_knows_it_is_prior_context", async () => {
      // Mitigation for prompt-injection risk: the stashed markdown is
      // LLM-emitted and untrusted from a "follow these instructions"
      // standpoint. A delimiter teaches the LLM to treat it as quoted.
      const { hook, assistantMsg } = await setupWithPlan("Plan X");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await hook.result.current.handleSend("change it", TEST_MODEL);
      });

      const [request] = mockPostAssistStream.mock.calls[0];
      // Loose contract — assert presence of structural framing, not the
      // exact prose, so we can iterate on the framing without breaking the
      // test on a wording tweak.
      expect(request.input_value).toMatch(/previous plan/i);
      expect(request.input_value).toMatch(/refinement/i);
    });

    it("should_not_prepend_anything_when_no_plan_is_in_refining_state", async () => {
      // Baseline: a fresh handleSend with no dismissed plan must pass the
      // user's text verbatim to the backend.
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("just a question", TEST_MODEL);
      });

      const [request] = mockPostAssistStream.mock.calls[0];
      expect(request.input_value).toBe("just a question");
    });

    it("should_record_only_the_users_raw_text_as_the_user_message_in_chat", async () => {
      // UX: the chat history should show the user's *original* message,
      // not the wrapped-with-prior-plan payload that went to the backend.
      const { hook, assistantMsg } = await setupWithPlan("Plan X");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await hook.result.current.handleSend("use Claude instead", TEST_MODEL);
      });

      const userMessages = hook.result.current.messages.filter(
        (m) => m.role === "user",
      );
      const lastUser = userMessages[userMessages.length - 1];
      expect(lastUser?.content).toBe("use Claude instead");
    });
  });

  describe("handleResetPlan clears stash and dismisses", () => {
    it("should_expose_a_handleResetPlan_function", () => {
      const { result } = renderHook(() => useAssistantChat());
      expect(typeof result.current.handleResetPlan).toBe("function");
    });

    it("should_mark_plan_as_dismissed_when_handleResetPlan_called", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan X");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      act(() => {
        hook.result.current.handleResetPlan(assistantMsg.id);
      });

      const updated = hook.result.current.messages.find(
        (m) => m.id === assistantMsg.id,
      );
      expect(updated?.planProposalStatus).toBe("dismissed");
    });

    it("should_not_prepend_stashed_plan_after_reset", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan X");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      act(() => {
        hook.result.current.handleResetPlan(assistantMsg.id);
      });
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await hook.result.current.handleSend("new question", TEST_MODEL);
      });

      const [request] = mockPostAssistStream.mock.calls[0];
      expect(request.input_value).toBe("new question");
      expect(request.input_value).not.toContain("Plan X");
    });
  });

  describe("stash auto-clears on next propose_plan", () => {
    it("should_clear_stash_when_a_new_propose_plan_event_arrives", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan v1");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      // Agent replans on the refinement turn. We mock the stream to emit a
      // new propose_plan event so the hook sees the agent did replan.
      emitPlan("Plan v2");
      await act(async () => {
        await hook.result.current.handleSend("use Claude instead", TEST_MODEL);
      });

      // Now send a third message with NO new dismiss. The stash should
      // be empty (cleared by the v2 plan), so input_value goes verbatim.
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);
      await act(async () => {
        await hook.result.current.handleSend("any followup", TEST_MODEL);
      });

      const [request] = mockPostAssistStream.mock.calls[0];
      expect(request.input_value).toBe("any followup");
      expect(request.input_value).not.toContain("Plan v1");
      expect(request.input_value).not.toContain("Plan v2");
    });
  });

  describe("isRefiningPlan flag exposed for input UX", () => {
    it("should_expose_isRefiningPlan_false_when_no_plan_is_refining", () => {
      const { result } = renderHook(() => useAssistantChat());
      expect(result.current.isRefiningPlan).toBe(false);
    });

    it("should_expose_isRefiningPlan_true_after_handleDismissPlan", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      expect(hook.result.current.isRefiningPlan).toBe(true);
    });

    it("should_flip_isRefiningPlan_back_to_false_after_reset", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });
      act(() => {
        hook.result.current.handleResetPlan(assistantMsg.id);
      });
      expect(hook.result.current.isRefiningPlan).toBe(false);
    });
  });

  describe("stash isolation across sessions", () => {
    it("should_clear_stash_when_handleClearHistory_called", async () => {
      const { hook, assistantMsg } = await setupWithPlan("Plan");
      act(() => {
        hook.result.current.handleDismissPlan(assistantMsg.id);
      });

      act(() => {
        hook.result.current.handleClearHistory();
      });
      mockPostAssistStream.mockClear();
      mockPostAssistStream.mockResolvedValue(undefined);

      await act(async () => {
        await hook.result.current.handleSend("fresh start", TEST_MODEL);
      });

      const [request] = mockPostAssistStream.mock.calls[0];
      expect(request.input_value).toBe("fresh start");
      expect(hook.result.current.isRefiningPlan).toBe(false);
    });
  });
});
