import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * Skip-all UX tests for `useAssistantChat`.
 *
 * Skip-all is a persistent preference that auto-approves every gate the
 * Assistant currently puts in front of the user:
 *   - plan-proposal Continue/Dismiss
 *   - destructive set_flow Continue/Dismiss
 *   - validated-component / written-file Continue
 *
 * The `/skip-all` slash command toggles the preference inline (no backend
 * round trip), and the chosen value persists across sessions via localStorage.
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
const STORAGE_KEY = "langflow-assistant-skip-all";

async function flushTimers() {
  // setTimeout(0) used to defer auto-approves to next tick.
  await act(async () => {
    jest.runOnlyPendingTimers();
    await Promise.resolve();
  });
}

describe("useAssistantChat — skip-all", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    mockPostAssistStream.mockResolvedValue(undefined);
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe("skipAll state surface", () => {
    it("should_default_skipAll_to_false_when_localStorage_is_empty", () => {
      const { result } = renderHook(() => useAssistantChat());
      expect(result.current.skipAll).toBe(false);
    });

    it("should_restore_skipAll_from_localStorage_on_mount", () => {
      localStorage.setItem(STORAGE_KEY, "true");
      const { result } = renderHook(() => useAssistantChat());
      expect(result.current.skipAll).toBe(true);
    });

    it("should_expose_toggleSkipAll_function", () => {
      const { result } = renderHook(() => useAssistantChat());
      expect(typeof result.current.toggleSkipAll).toBe("function");
    });

    it("should_flip_skipAll_and_persist_when_toggleSkipAll_called", () => {
      const { result } = renderHook(() => useAssistantChat());

      act(() => {
        result.current.toggleSkipAll();
      });

      expect(result.current.skipAll).toBe(true);
      expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
    });

    it("should_remove_storage_key_when_toggleSkipAll_flips_back_to_false", () => {
      localStorage.setItem(STORAGE_KEY, "true");
      const { result } = renderHook(() => useAssistantChat());

      act(() => {
        result.current.toggleSkipAll();
      });

      expect(result.current.skipAll).toBe(false);
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    });
  });

  describe("/skip-all slash command", () => {
    it("should_not_call_postAssistStream_when_input_is_slash_skip_all", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("/skip-all", TEST_MODEL);
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
    });

    it("should_toggle_skipAll_when_input_is_slash_skip_all", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("/skip-all", TEST_MODEL);
      });

      expect(result.current.skipAll).toBe(true);
    });

    it("should_treat_slash_skip_all_with_surrounding_whitespace_as_a_command", async () => {
      // Users tend to type "  /skip-all  " — trimming is the only friendly
      // behavior. Spaces inside the token (e.g. "/ skip-all") are NOT a
      // command and go through normal handleSend.
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("  /skip-all  ", TEST_MODEL);
      });

      expect(mockPostAssistStream).not.toHaveBeenCalled();
      expect(result.current.skipAll).toBe(true);
    });

    it("should_add_an_inline_info_message_describing_the_new_state", async () => {
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("/skip-all", TEST_MODEL);
      });

      const messages = result.current.messages;
      const lastAssistantMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant");
      // Loose contract — copy can be iterated without breaking the test.
      expect(lastAssistantMsg?.content.toLowerCase()).toContain("skip");
      expect(lastAssistantMsg?.content.toLowerCase()).toContain("enabled");
    });

    it("should_announce_disabled_state_when_toggling_off", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("/skip-all", TEST_MODEL);
      });

      const lastAssistantMsg = [...result.current.messages]
        .reverse()
        .find((m) => m.role === "assistant");
      expect(lastAssistantMsg?.content.toLowerCase()).toContain("disabled");
    });

    it("should_pass_input_to_backend_when_text_only_starts_with_slash_skip_all", async () => {
      // Anti-foot-gun: only the EXACT command toggles. A user typing
      // "/skip-all please" wants to actually send a message that
      // happens to contain those tokens.
      const { result } = renderHook(() => useAssistantChat());

      await act(async () => {
        await result.current.handleSend("/skip-all please", TEST_MODEL);
      });

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
      expect(result.current.skipAll).toBe(false);
    });
  });

  describe("synthetic approval message stays hidden in skip-all", () => {
    it("should_not_render_the_approval_text_as_a_user_message_when_skipAll_on", async () => {
      // The "User approved the plan. Proceed with the build." string is a
      // backend signal, not user-authored content. Showing it in the chat
      // is noise the user explicitly asked us to remove. The text MUST
      // still reach the backend (covered by the next test).
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      mockPostAssistStream.mockResolvedValue(undefined);

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();

      const userMessageContents = result.current.messages
        .filter((m) => m.role === "user")
        .map((m) => m.content);
      // The only visible user message is the original prompt.
      expect(userMessageContents).toEqual(["build a chatbot"]);
      expect(userMessageContents).not.toContain(
        "User approved the plan. Proceed with the build.",
      );
    });

    it("should_still_send_the_approval_text_to_the_backend_when_skipAll_on", async () => {
      // The synthetic message is hidden from the chat, but the backend
      // call MUST still carry the approval string — otherwise the agent
      // wouldn't know the user approved and would replan.
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      mockPostAssistStream.mockResolvedValue(undefined);

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();

      const secondCall = mockPostAssistStream.mock.calls[1];
      expect(secondCall[0].input_value.toLowerCase()).toContain("approve");
    });
  });

  describe("auto-approve propose_plan when skipAll is on", () => {
    it("should_auto_send_an_approval_turn_when_propose_plan_arrives_and_skipAll_on", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      mockPostAssistStream.mockResolvedValue(undefined);

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });

      // Auto-approve is deferred so isProcessing has time to reset.
      await flushTimers();

      // postAssistStream called twice: once for the initial send, once for
      // the auto-approval turn.
      expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
      const secondCallInput = mockPostAssistStream.mock.calls[1][0]
        .input_value as string;
      expect(secondCallInput.toLowerCase()).toContain("approve");
    });

    it("should_not_auto_approve_when_skipAll_is_off", async () => {
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();

      expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
    });
  });

  describe("single-message continuity across skip-all bridge", () => {
    // The user perceives a "blink" when (a) isProcessing flips false
    // between turns and (b) the assistant message slot is swapped. Both
    // problems are fixed by reusing the SAME message slot in "streaming"
    // status throughout the auto-approval bridge.

    function planThenBuild() {
      // Turn 1: agent emits propose_plan and ends.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onToken({
            event: "token",
            chunk: "I am proposing a plan.",
          });
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      // Turn 2: agent builds the flow and returns the final result.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: { data: { nodes: [{ id: "n1" }], edges: [] } },
          });
          callbacks.onComplete({
            event: "complete",
            data: {
              result: "Created flow Agent + WebCrawler.",
              validated: true,
            },
          });
        },
      );
    }

    it("should_keep_messages_length_at_user_plus_one_assistant_after_auto_approve", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      planThenBuild();

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();
      await flushTimers();

      // One user message + ONE assistant message. The auto-approval
      // re-uses the same assistant slot instead of appending a second
      // assistant message.
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].role).toBe("user");
      expect(result.current.messages[1].role).toBe("assistant");
    });

    it("should_keep_the_same_assistant_message_id_across_both_turns", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      planThenBuild();

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      // After act flushes, turn 1 has settled. The auto-approve setTimeout
      // is queued but not fired yet (fake timers).
      const idAfterPlan = result.current.messages.find(
        (m) => m.role === "assistant",
      )?.id;
      expect(idAfterPlan).toBeDefined();

      await flushTimers();
      await flushTimers();

      const idAfterBuild = result.current.messages.find(
        (m) => m.role === "assistant",
      )?.id;
      expect(idAfterBuild).toBeDefined();
      expect(idAfterBuild).toBe(idAfterPlan);
    });

    it("should_replace_planning_preamble_with_build_result_content", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      planThenBuild();

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();
      await flushTimers();

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant",
      );
      // The "I am proposing a plan." preamble must be gone — the slot
      // now carries the actual build result.
      expect(assistantMsg?.content).toBe("Created flow Agent + WebCrawler.");
      expect(assistantMsg?.content).not.toContain("proposing a plan");
    });

    it("should_keep_assistant_status_streaming_during_the_bridge", async () => {
      // Snapshot the assistant message status while turn 1 has completed
      // but turn 2 hasn't fired yet. With the bridge in place the status
      // must NOT flip to "complete" — that's what would hide the rich
      // loading state and cause the blink.
      localStorage.setItem(STORAGE_KEY, "true");
      let statusObservedDuringBridge: string | undefined;
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          // Capture state at the moment turn 2 starts.
          // We can't peek React state from here, but the hook test below
          // asserts the status after the dust settles to complete.
          // Keep this mock simple — just resolve.
          callbacks.onComplete({
            event: "complete",
            data: { result: "ok", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      // Snapshot BEFORE flushing the auto-approve timer — at this point
      // turn 1 has completed (onComplete fired) but turn 2 hasn't begun.
      statusObservedDuringBridge = result.current.messages.find(
        (m) => m.role === "assistant",
      )?.status;

      await flushTimers();
      await flushTimers();

      // The whole point of the bridge: status stays "streaming" so the
      // rich loading state stays mounted.
      expect(statusObservedDuringBridge).toBe("streaming");
    });
  });

  describe("plan card is hidden in skip-all mode", () => {
    it("should_not_set_pendingPlanProposal_when_propose_plan_arrives_and_skipAll_on", async () => {
      // The card adds friction even when it auto-approves (the user sees
      // "Proposed plan" → "Plan approved" flash). Skip-all should make the
      // gate invisible entirely.
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );
      mockPostAssistStream.mockResolvedValue(undefined);

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });
      await flushTimers();

      const assistantMsg = result.current.messages.find(
        (m) => m.role === "assistant" && m.content !== "",
      );
      // Either the message doesn't exist with a pendingPlanProposal at
      // all, or pendingPlanProposal is undefined — both mean "no card
      // ever rendered". We assert the latter to be precise.
      const planMsgs = result.current.messages.filter(
        (m) => m.pendingPlanProposal,
      );
      expect(planMsgs).toEqual([]);
      // And the auto-approval still happened.
      expect(mockPostAssistStream).toHaveBeenCalledTimes(2);
      void assistantMsg;
    });

    it("should_still_set_pendingPlanProposal_when_skipAll_is_off", async () => {
      // Regression baseline: the card MUST render when skipAll is off.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "propose_plan",
            markdown: "Plan body",
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend("build a chatbot", TEST_MODEL);
      });

      const planMsg = result.current.messages.find(
        (m) => m.pendingPlanProposal,
      );
      expect(planMsg?.pendingPlanProposal?.markdown).toBe("Plan body");
      expect(planMsg?.planProposalStatus).toBe("pending");
    });
  });

  describe("auto-apply set_flow when skipAll is on", () => {
    it("should_apply_flow_to_canvas_immediately_when_set_flow_arrives_and_skipAll_on", async () => {
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: {
              data: { nodes: [{ id: "n1" }], edges: [{ id: "e1" }] },
              name: "Auto-applied",
            },
          });
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
      await flushTimers();

      // Canvas was mutated without the user clicking Continue on the
      // flow-proposal card.
      expect(mockSetNodes).toHaveBeenCalled();
      expect(mockSetEdges).toHaveBeenCalled();
    });

    it("should_not_mount_pendingFlowProposal_when_skipAll_is_on", async () => {
      // The direct-apply path means the proposal-card state never gets
      // populated. This eliminates the setTimeout/closure race that
      // happened on the *second* turn of an auto-approved plan (where
      // pendingFlowProposal would have been read via stale messages).
      localStorage.setItem(STORAGE_KEY, "true");
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: {
              data: { nodes: [{ id: "n1" }], edges: [] },
            },
          });
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
      await flushTimers();

      const flowMsgs = result.current.messages.filter(
        (m) => m.pendingFlowProposal,
      );
      expect(flowMsgs).toEqual([]);
    });

    it("should_keep_proposal_gated_when_skipAll_is_off", async () => {
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            flow: {
              data: { nodes: [{ id: "n1" }], edges: [] },
            },
          });
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
      await flushTimers();

      // Default behavior: canvas untouched until the user clicks Continue.
      expect(mockSetNodes).not.toHaveBeenCalled();
      expect(mockSetEdges).not.toHaveBeenCalled();
    });

    it("should_auto_apply_set_flow_when_auto_apply_flag_is_set_even_with_skipAll_off", async () => {
      // Compound pipeline: backend tags set_flow with auto_apply (the user
      // asked to clear+replace the canvas). Must apply directly, no card,
      // even though skip-all is OFF.
      mockPostAssistStream.mockImplementationOnce(
        async (_req: unknown, callbacks: Record<string, Function>) => {
          callbacks.onFlowUpdate({
            event: "flow_update",
            action: "set_flow",
            auto_apply: true,
            flow: { data: { nodes: [{ id: "n1" }], edges: [{ id: "e1" }] } },
          });
          callbacks.onComplete({
            event: "complete",
            data: { result: "", validated: true },
          });
        },
      );

      const { result } = renderHook(() => useAssistantChat());
      await act(async () => {
        await result.current.handleSend(
          "create a component and a flow",
          TEST_MODEL,
        );
      });
      await flushTimers();

      expect(mockSetNodes).toHaveBeenCalled();
      expect(mockSetEdges).toHaveBeenCalled();
      expect(
        result.current.messages.filter((m) => m.pendingFlowProposal),
      ).toEqual([]);
    });
  });
});
