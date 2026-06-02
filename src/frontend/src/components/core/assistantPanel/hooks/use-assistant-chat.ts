import { useUpdateNodeInternals } from "@xyflow/react";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ShortUniqueId from "short-unique-id";
import {
  type AgenticFlowUpdateEvent,
  type AgenticStepType,
  postAssistStream,
} from "@/controllers/API/queries/agentic";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { BASE_URL_API } from "@/customization/config-constants";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType } from "@/types/api";
import type {
  AssistantMessage,
  AssistantModel,
} from "../assistant-panel.types";
import { applyFlowUpdate as applyFlowUpdateImpl } from "../helpers/apply-flow-update";
import {
  buildRefinementInput,
  buildTaskFromEvent,
} from "../helpers/assistant-event-mappers";
import { mergeFlowIntoCanvas } from "../helpers/merge-flow-into-canvas";
import { readSkipAll, writeSkipAll } from "./skip-all-storage";

const uid = new ShortUniqueId();
const AGENTIC_SESSION_PREFIX = "agentic_";
const SKIP_ALL_COMMAND = "/skip-all";
const SKIP_ALL_APPROVAL_TEXT =
  "User approved the plan. Proceed with the build.";
// Backend protocol string (never user-authored). Sent as a silent
// continuation turn once the user resolves a man-in-the-loop edit diff
// card with at least one applied change, so the agent's "execution stack"
// survives the approval boundary and it can finish the rest of the
// original request (e.g. running the flow). Must stay byte-identical to
// `EDIT_CONTINUATION_INPUT` in
// src/backend/base/langflow/agentic/services/flow_types.py.
const EDIT_CONTINUATION_INPUT =
  "The proposed canvas edits were applied. Continue with the remaining steps of my previous request (for example, running the flow). If editing was the entire request, just confirm briefly.";

/**
 * Fire-and-forget call to wipe the calling user's session-scoped state
 * (registered components, conversation buffer). Best-effort: a network
 * failure must not block the user from typing — the next request would
 * just see stale components for one turn.
 */
async function fireSessionReset(sessionId: string): Promise<void> {
  try {
    await fetch(
      `${BASE_URL_API}agentic/sessions/reset?session_id=${encodeURIComponent(sessionId)}`,
      { method: "POST", credentials: "include" },
    );
  } catch {
    // Swallow — degrades gracefully (stale components, next turn).
  }
}

interface UseAssistantChatReturn {
  messages: AssistantMessage[];
  sessionId: string;
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
  handleSend: (
    content: string,
    model: AssistantModel | null,
    options?: { silent?: boolean },
  ) => Promise<void>;
  handleApprove: (messageId: string, componentCode?: string) => Promise<void>;
  handleUpdateFlowAction: (
    messageId: string,
    actionId: string,
    status: "applied" | "dismissed",
  ) => Promise<void>;
  handleApplyFlowProposal: (
    messageId: string,
    mode?: "replace" | "add",
  ) => void;
  handleDismissFlowProposal: (messageId: string) => void;
  handleApprovePlan: (messageId: string) => Promise<void>;
  handleDismissPlan: (messageId: string) => void;
  handleResetPlan: (messageId: string) => void;
  /**
   * Mark the component validation gate as acknowledged on the message.
   * Persisted across remounts so panel close/reopen doesn't bring the
   * loading card back after the user already pressed Continue.
   */
  handleAcknowledgeValidation: (messageId: string) => void;
  /**
   * True while a previously-proposed plan has been dismissed by the user and
   * is awaiting refinement. The UI uses this to swap the input placeholder
   * and amber the plan card.
   */
  isRefiningPlan: boolean;
  /**
   * Persistent power-user preference: when true, every gate that would
   * otherwise require an explicit Continue click auto-approves. Restored
   * from localStorage on mount.
   */
  skipAll: boolean;
  /** Flip the skipAll preference and persist the change. */
  toggleSkipAll: () => void;
  handleRetry: (messageId: string) => void;
  handleStopGeneration: () => void;
  handleClearHistory: () => void;
  loadSession: (id: string, msgs: AssistantMessage[]) => void;
}

// Known size debt: this hook is over the 500-line ceiling. The bulk is
// `handleSend` (~390 lines) — the SSE pump that interleaves token streaming,
// flow events, plan/file events, retry handling, and cancellation. Cleaving
// it further requires a state-machine refactor (or moving each SSE event
// class into its own reducer-style handler with shared context), which is a
// dedicated piece of work — out of scope for the cosmetic / UX pass that
// introduced this comment. Helpers already lifted: `applyFlowUpdate`,
// `buildTaskFromEvent`, `buildRefinementInput`.
export function useAssistantChat(): UseAssistantChatReturn {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<AgenticStepType | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastModelRef = useRef<AssistantModel | null>(null);
  // Per-send flag: once a `set_flow` event arrives, subsequent non-`edit_field`
  // events must be buffered too (defensive against mixed runs). Reset at the
  // start of every handleSend to avoid leaking state across requests.
  const proposalPendingRef = useRef<boolean>(false);
  // Holds the markdown of the LAST plan the user dismissed-but-not-reset, so
  // the next handleSend can re-inject it as context for the LLM. One-shot:
  // cleared by handleResetPlan, by a fresh propose_plan event, and on
  // session boundaries (handleClearHistory, loadSession).
  const dismissedPlanMarkdownRef = useRef<string | null>(null);
  const [isRefiningPlan, setIsRefiningPlan] = useState<boolean>(false);
  // Initialized from localStorage so a power user's preference survives
  // page reloads and new sessions. The ref tracks the latest value for
  // event-handler closures that captured the initial state.
  const [skipAll, setSkipAll] = useState<boolean>(() => readSkipAll());
  const skipAllRef = useRef<boolean>(skipAll);
  skipAllRef.current = skipAll;
  // Queues an assistant-message id that needs auto-approve once the
  // current stream's onComplete drains. Using a ref (not state) keeps
  // the value visible to event handlers in the same tick.
  const autoApprovePlanRef = useRef<string | null>(null);
  // Lazy reference to handleApprovePlan, defined later in this hook. We
  // can't include it as a dep of handleSend (circular), so we capture
  // its latest identity via assign-after-declare below.
  const handleApprovePlanRef = useRef<((id: string) => Promise<void>) | null>(
    null,
  );
  const sessionIdRef = useRef<string>(
    `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`,
  );
  const [sessionId, setSessionId] = useState<string>(sessionIdRef.current);

  // WS-3 / RC-3: components are session-scoped, NOT wiped on mount.
  // A panel re-open / page reload must keep the user's generated
  // components alive so a component made in one turn is still usable in
  // the next request (report #3, screenshot 2). The registry is wiped
  // ONLY on an explicit New session (`handleClearHistory`) — never here.
  // `loadSession` also does not wipe (user is continuing prior work).

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const addComponent = useAddComponent();
  const saveFlow = useSaveFlow();
  // Assistant-message ids that already fired their edit-approval
  // continuation. A ref (not state) so the guard is visible synchronously
  // within the same tick the diff card is resolved.
  const continuedEditMsgIds = useRef<Set<string>>(new Set());
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();
  // ReactFlow caches handle positions per node. When we mutate node data
  // that changes which handles are rendered or their position (e.g. flipping
  // _connectionMode on a ModelInput, switching selected_output, replacing a
  // node via set_flow), we MUST notify ReactFlow so existing edges find
  // their endpoints — otherwise the edge stays in state but renders as
  // disconnected.
  const updateNodeInternals = useUpdateNodeInternals();
  // Live-canvas SSE applier. Delegated to a pure helper so the hook keeps a
  // single responsibility (streaming + message state) and so the per-event
  // switch can grow without dragging this file over the size limit. The
  // empty dep list mirrors xyflow's contract that `updateNodeInternals` is a
  // stable reference for the component's lifetime.
  const applyFlowUpdate = useCallback(
    (event: AgenticFlowUpdateEvent) => {
      applyFlowUpdateImpl(event, updateNodeInternals);
    },
    [updateNodeInternals],
  );

  const updateMessage = useCallback(
    (
      messageId: string,
      updater: (msg: AssistantMessage) => Partial<AssistantMessage>,
    ) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId ? { ...msg, ...updater(msg) } : msg,
        ),
      );
    },
    [],
  );

  const handleSend = useCallback(
    async (
      content: string,
      model: AssistantModel | null,
      options?: {
        silent?: boolean;
        internal?: boolean;
        reuseAssistantMessageId?: string;
      },
    ) => {
      // ``internal`` bypasses the processing guard so the skip-all bridge
      // can chain a second backend call without waiting for isProcessing
      // to flip false (which would visually unmount the loading state).
      if (!options?.internal && isProcessing) return;
      // ``silent`` skips appending a visible user message but still adds
      // the assistant message slot needed as anchor for streaming events.
      // ``reuseAssistantMessageId`` goes one step further: it skips
      // creating a new message entirely and resets the existing slot in
      // place. Together with silent+internal these make the skip-all
      // auto-approval invisible to the user — one continuous "streaming"
      // message across two backend turns.
      const silent = options?.silent === true;
      const reuseId = options?.reuseAssistantMessageId;

      // Local slash command: toggles the persistent skip-all preference
      // and emits an inline info message. Exact match only — typing
      // "/skip-all please" is a real prompt that happens to start with
      // those tokens and must reach the backend.
      if (content.trim() === SKIP_ALL_COMMAND) {
        const next = !skipAllRef.current;
        skipAllRef.current = next;
        setSkipAll(next);
        writeSkipAll(next);
        const echoUserId = uid.randomUUID(10);
        const ackId = uid.randomUUID(10);
        const announcement = next
          ? "Skip-all mode enabled. Plans, flow proposals, and validated components will be approved automatically."
          : "Skip-all mode disabled. Plans, flow proposals, and validated components will wait for your Continue click.";
        setMessages((prev) => [
          ...prev,
          {
            id: echoUserId,
            role: "user",
            content,
            timestamp: new Date(),
            status: "complete",
          },
          {
            id: ackId,
            role: "assistant",
            content: announcement,
            timestamp: new Date(),
            status: "complete",
          },
        ]);
        return;
      }

      if (!model?.provider || !model?.name) {
        return;
      }

      lastModelRef.current = model;

      const userMessage: AssistantMessage = {
        id: uid.randomUUID(10),
        role: "user",
        content,
        timestamp: new Date(),
        status: "complete",
      };

      const assistantMessageId = reuseId ?? uid.randomUUID(10);
      const assistantMessage: AssistantMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "streaming",
      };

      if (reuseId) {
        // Reset the existing slot so turn 2's events overwrite the
        // planning preamble. Status stays "streaming" so the rich
        // loading state never unmounts.
        updateMessage(reuseId, () => ({
          content: "",
          status: "streaming" as const,
          progress: undefined,
          error: undefined,
          pendingPlanProposal: undefined,
          planProposalStatus: undefined,
          hidden: false,
        }));
      } else {
        setMessages((prev) =>
          silent
            ? [...prev, assistantMessage]
            : [...prev, userMessage, assistantMessage],
        );
      }
      setIsProcessing(true);
      proposalPendingRef.current = false;

      // If the user dismissed a prior plan and is now sending a refinement,
      // re-inject the dismissed plan markdown as context so the LLM (which
      // has no server-side conversation history) knows it is replanning.
      // The delimiter framing tells the LLM the block is quoted prior
      // context, not new instructions.
      const stashedPlan = dismissedPlanMarkdownRef.current;
      const inputValue = stashedPlan
        ? buildRefinementInput(stashedPlan, content)
        : content;

      // Abort any still-in-flight stream before starting a new one.
      // internal:true sends (skip-all bridge / edit-continuation) bypass
      // the isProcessing guard, so without this the previous SSE reader
      // is leaked and two pumps mutate the same message concurrently.
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      const completedSteps: AgenticStepType[] = [];
      let currentStepTracked: AgenticStepType | null = null;

      try {
        await postAssistStream(
          {
            flow_id: currentFlowId || "",
            input_value: inputValue,
            provider: model?.provider,
            model_name: model?.name,
            session_id: sessionIdRef.current,
          },
          {
            onProgress: (event) => {
              // When transitioning to a new step, mark the previous one as completed
              if (currentStepTracked && event.step !== currentStepTracked) {
                completedSteps.push(currentStepTracked);
              }
              currentStepTracked = event.step;

              setCurrentStep(event.step);
              updateMessage(assistantMessageId, (msg) => ({
                progress: {
                  step: event.step,
                  attempt: event.attempt,
                  maxAttempts: event.max_attempts,
                  message: event.message,
                  error: event.error,
                  // Preserve componentCode and className from previous
                  // progress if the new event doesn't include them
                  className: event.class_name ?? msg.progress?.className,
                  componentCode:
                    event.component_code ?? msg.progress?.componentCode,
                },
                completedSteps: [...completedSteps],
              }));
            },
            onToken: (event) => {
              updateMessage(assistantMessageId, (msg) => ({
                content: msg.content + event.chunk,
              }));
            },
            onFlowPreview: (event) => {
              applyFlowUpdate({
                event: "flow_update",
                action: "set_flow",
                flow: event.flow,
              });
              updateMessage(assistantMessageId, () => ({
                flowPreview: {
                  flow: event.flow,
                  name: event.name,
                  nodeCount: event.node_count,
                  edgeCount: event.edge_count,
                  graph: event.graph,
                },
              }));
            },
            onFlowUpdate: (event) => {
              if (event.action === "edit_field") {
                updateMessage(assistantMessageId, (msg) => ({
                  flowActions: [
                    ...(msg.flowActions ?? []),
                    {
                      id: event.id as string,
                      type: "edit_field" as const,
                      description: event.description as string,
                      component_id: event.component_id as string,
                      component_type: event.component_type as string,
                      field: event.field as string,
                      old_value: event.old_value,
                      new_value: event.new_value,
                      patch: event.patch as {
                        op: string;
                        path: string;
                        value: unknown;
                      }[],
                      status: "pending" as const,
                    },
                  ],
                }));
                return;
              }
              if (event.action === "propose_plan") {
                // BUILD-mode planning gate: the agent emits a markdown plan
                // and stops. Canvas is untouched — the user must Continue
                // (triggers handleApprovePlan) or Dismiss (handleDismissPlan)
                // before the agent moves on to search/describe/build_flow.
                // A fresh plan supersedes any stashed dismissed plan: the
                // refinement was consumed and replanned, so the prior
                // context must not pile up onto the next handleSend.
                dismissedPlanMarkdownRef.current = null;
                setIsRefiningPlan(false);
                if (skipAllRef.current) {
                  // Skip-all bridge: queue the auto-approve. Clear the
                  // preamble the LLM streamed before the tool call so the
                  // chat reads as one continuous "Generating flow…" until
                  // turn 2 fills the slot with the actual result.
                  autoApprovePlanRef.current = assistantMessageId;
                  updateMessage(assistantMessageId, () => ({ content: "" }));
                  return;
                }
                const markdown =
                  typeof event.markdown === "string" ? event.markdown : "";
                updateMessage(assistantMessageId, () => ({
                  pendingPlanProposal: { markdown },
                  planProposalStatus: "pending" as const,
                }));
                return;
              }
              if (event.action === "set_flow") {
                if (skipAllRef.current || event.auto_apply === true) {
                  // Skip-all OR a compound-pipeline auto-apply (the user
                  // explicitly asked to clear+replace the canvas): apply
                  // directly using the event
                  // payload — no proposal-card state, no setTimeout/queue
                  // race. The earlier "queue and drain in onComplete"
                  // approach was vulnerable to a stale-closure read of
                  // `messages` when set_flow arrived in the *second* turn
                  // of an auto-approved plan.
                  applyFlowUpdate({
                    event: "flow_update",
                    action: "set_flow",
                    flow: event.flow,
                  });
                  return;
                }
                // Build-from-scratch path: buffer the entire flow into a
                // proposal the user must Accept/Dismiss. Canvas stays
                // untouched until handleApplyFlowProposal replays it.
                proposalPendingRef.current = true;
                const flow = (event.flow ?? {}) as Record<string, unknown>;
                const data = (flow.data ?? {}) as {
                  nodes?: unknown[];
                  edges?: unknown[];
                };
                updateMessage(assistantMessageId, () => ({
                  pendingFlowProposal: {
                    flow,
                    name: (flow.name as string | undefined) ?? undefined,
                    nodeCount: (data.nodes ?? []).length,
                    edgeCount: (data.edges ?? []).length,
                    tailUpdates: [],
                  },
                  flowProposalStatus: "pending" as const,
                }));
                return;
              }
              // Incremental edits — once a proposal is pending in this send,
              // buffer subsequent events into tailUpdates (defensive: the
              // agent prompt forbids mixed runs, but we don't want partial
              // canvas state if it happens). Otherwise apply live.
              if (proposalPendingRef.current) {
                updateMessage(assistantMessageId, (msg) =>
                  msg.pendingFlowProposal
                    ? {
                        pendingFlowProposal: {
                          ...msg.pendingFlowProposal,
                          tailUpdates: [
                            ...(msg.pendingFlowProposal.tailUpdates ?? []),
                            event,
                          ],
                        },
                      }
                    : {},
                );
                return;
              }
              applyFlowUpdate(event);
              // Surface the incremental mutation as a checklist entry the
              // user can see in the chat. Dedup against the latest entry
              // with the same (action, identity) so SSE replays don't
              // produce phantom duplicates.
              const newTask = buildTaskFromEvent(event);
              if (newTask) {
                updateMessage(assistantMessageId, (msg) => {
                  const existing = msg.buildTasks ?? [];
                  if (
                    existing.some(
                      (t) =>
                        t.action === newTask.action &&
                        t.componentId === newTask.componentId &&
                        t.sourceId === newTask.sourceId &&
                        t.targetId === newTask.targetId,
                    )
                  ) {
                    return {};
                  }
                  return { buildTasks: [...existing, newTask] };
                });
              }
            },
            onFileWritten: (event) => {
              // Append a WrittenFile entry for each successful write/edit so
              // the message can render one card per file in arrival order.
              updateMessage(assistantMessageId, (msg) => ({
                writtenFiles: [
                  ...(msg.writtenFiles ?? []),
                  {
                    action: event.action,
                    path: event.path,
                    size: event.size,
                    receivedAt: Date.now(),
                    content: event.content,
                  },
                ],
              }));
            },
            onComplete: (event) => {
              const planMsgId = autoApprovePlanRef.current;
              if (planMsgId) {
                // Skip-all bridge: turn 1 completed and we have a queued
                // auto-approve. Do NOT mark the slot complete or reset
                // isProcessing/currentStep — that would unmount the rich
                // loading state and idle the input placeholder, which is
                // exactly the blink the user reported. Chain straight
                // into turn 2; ``internal: true`` on the next handleSend
                // skips the processing guard.
                autoApprovePlanRef.current = null;
                setTimeout(() => {
                  handleApprovePlanRef.current?.(planMsgId);
                }, 0);
                return;
              }
              updateMessage(assistantMessageId, () => ({
                status: "complete" as const,
                content: event.data.result || "",
                // Whether approving a man-in-the-loop edit on THIS message
                // should fire the continuation turn (a deferred run/test was
                // requested). A pure edit leaves this false so approving it
                // does NOT spawn a redundant second message.
                continuationExpected: event.data.continuation_expected === true,
                result: {
                  content: event.data.result || "",
                  validated: event.data.validated,
                  hasFlow: event.data.has_flow,
                  className: event.data.class_name,
                  componentCode: event.data.component_code,
                  validationAttempts: event.data.validation_attempts,
                  validationError: event.data.validation_error,
                },
                // Per-turn LLM cost reported by the backend. Stored in the
                // message so panel close/reopen still shows the badge.
                // Duration is converted to milliseconds to match the units
                // ``MessageMetadata`` (the playground renderer reused here)
                // expects in its ``duration`` prop.
                usage: event.data.usage,
                duration:
                  typeof event.data.duration_seconds === "number"
                    ? event.data.duration_seconds * 1000
                    : undefined,
              }));
              setCurrentStep(null);
              setIsProcessing(false);
            },
            onError: (event) => {
              updateMessage(assistantMessageId, () => ({
                status: "error" as const,
                error: event.message,
              }));
              setCurrentStep(null);
              setIsProcessing(false);
            },
            onCancelled: () => {
              updateMessage(assistantMessageId, () => ({
                status: "cancelled" as const,
                progress: undefined,
              }));
              setCurrentStep(null);
              setIsProcessing(false);
            },
          },
          abortControllerRef.current.signal,
        );
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          updateMessage(assistantMessageId, () => ({
            status: "error" as const,
            error: t("assistant.failedToConnect"),
          }));
        }
        setCurrentStep(null);
        setIsProcessing(false);
      }
    },
    [isProcessing, currentFlowId, updateMessage],
  );

  const handleApprove = useCallback(
    async (messageId: string, componentCode?: string) => {
      const message = messages.find((m) => m.id === messageId);
      const code = componentCode || message?.result?.componentCode;
      if (!code) return;

      try {
        // Backend builds the full frontend_node from code validation; empty placeholder is expected
        const response = await validateComponent({
          code,
          frontend_node: {} as APIClassType,
        });

        if (response.data) {
          addComponent(response.data, response.type || "CustomComponent");
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        console.error("Failed to validate or add component to canvas:", error);
        // Show validation failure to the user instead of silently swallowing
        updateMessage(messageId, () => ({
          result: {
            content: code,
            validated: false,
            componentCode: code,
            validationError: `Failed to add component: ${errorMessage}`,
          },
        }));
      }
    },
    [messages, validateComponent, addComponent, updateMessage],
  );

  const handleRetry = useCallback(
    (messageId: string) => {
      // Find the failed assistant message and the user message before it
      const msgIndex = messages.findIndex((m) => m.id === messageId);
      if (msgIndex < 1) return;

      const userMessage = messages
        .slice(0, msgIndex)
        .reverse()
        .find((m) => m.role === "user");
      if (!userMessage?.content || !lastModelRef.current) return;

      // Remove the failed assistant message so a fresh one is created by handleSend
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      handleSend(userMessage.content, lastModelRef.current);
    },
    [messages, handleSend],
  );

  const handleUpdateFlowAction = useCallback(
    async (
      messageId: string,
      actionId: string,
      status: "applied" | "dismissed",
    ) => {
      updateMessage(messageId, (msg) => ({
        flowActions: msg.flowActions?.map((a) =>
          a.id === actionId ? { ...a, status } : a,
        ),
      }));

      // Edit-approval continuation ("execution stack"): the diff card is a
      // man-in-the-loop gate. Once every action on this message has left
      // "pending" with >=1 applied, the agent's deferred steps (e.g. the
      // run the user also asked for) must resume. The backend reads the
      // working flow from the DB by flow_id, so the canvas MUST be
      // persisted BEFORE the continuation turn or the run would see the
      // pre-edit value. Fires exactly once per message; a dismiss-only
      // resolution does not continue (the change was rejected).
      const msg = messages.find((m) => m.id === messageId);
      const actions = (msg?.flowActions ?? []).map((a) =>
        a.id === actionId ? { ...a, status } : a,
      );
      if (actions.length === 0) return;
      const stillPending = actions.some((a) => a.status === "pending");
      const anyApplied = actions.some((a) => a.status === "applied");
      if (stillPending || !anyApplied) return;
      // Only resume when the original request actually deferred a step
      // (e.g. "...and run it"). A pure edit must NOT spawn a second
      // assistant message — backend computes this deterministically.
      if (!msg?.continuationExpected) return;
      if (continuedEditMsgIds.current.has(messageId)) return;
      if (!lastModelRef.current) return;
      continuedEditMsgIds.current.add(messageId);

      await saveFlow();
      await handleSend(EDIT_CONTINUATION_INPUT, lastModelRef.current, {
        silent: true,
        internal: true,
      });
    },
    [messages, updateMessage, saveFlow, handleSend],
  );

  const handleApplyFlowProposal = useCallback(
    (messageId: string, mode: "replace" | "add" = "replace") => {
      const message = messages.find((m) => m.id === messageId);
      const proposal = message?.pendingFlowProposal;
      if (!proposal) return;

      if (mode === "add") {
        // Additive: merge the proposal into the current canvas state.
        // ID collisions are remapped, edges are rewritten to follow the
        // remap, and positions are offset to the right of the existing
        // bounding box so the new flow doesn't overlap.
        const store = useFlowStore.getState();
        const flow = proposal.flow as {
          data?: { nodes?: unknown[]; edges?: unknown[] };
        };
        const proposalNodes =
          (flow.data?.nodes as Array<{
            id: string;
            position: { x: number; y: number };
          }>) ?? [];
        const proposalEdges =
          (flow.data?.edges as Array<{
            id: string;
            source: string;
            target: string;
          }>) ?? [];
        const merged = mergeFlowIntoCanvas(
          store.nodes as Array<{
            id: string;
            position: { x: number; y: number };
          }>,
          store.edges as Array<{
            id: string;
            source: string;
            target: string;
          }>,
          { nodes: proposalNodes, edges: proposalEdges },
        );
        store.setNodes(merged.nodes as never[]);
        store.setEdges(merged.edges as never[]);
      } else {
        // Replace (legacy default): destructive overwrite via the
        // existing set_flow path. Tail updates still replay in order.
        applyFlowUpdate({
          event: "flow_update",
          action: "set_flow",
          flow: proposal.flow,
        });
      }
      for (const tail of proposal.tailUpdates ?? []) {
        applyFlowUpdate(tail);
      }

      // Keep ``pendingFlowProposal`` on the message — the preview card
      // continues to render in the muted "applied" state, mirroring the
      // component-generation flow where the result card stays after Add to
      // Canvas. Clearing the proposal here would erase the visual record of
      // what the user accepted.
      updateMessage(messageId, () => ({
        flowProposalStatus: "applied" as const,
      }));

      // Revert to ``pending`` after the success badge has been on screen
      // long enough to register — lets the user re-apply the same proposal
      // (e.g., they edited the canvas and want to overwrite it again).
      // Matches the 3s pattern used by the legacy "Add to Flow" path.
      setTimeout(() => {
        updateMessage(messageId, (msg) =>
          // Only revert if the message is still in "applied" state. If the
          // user already dismissed or sent a new request, leave it alone.
          msg.flowProposalStatus === "applied"
            ? { flowProposalStatus: "pending" }
            : {},
        );
      }, 3000);
    },
    [messages, applyFlowUpdate, updateMessage],
  );

  const handleDismissFlowProposal = useCallback(
    (messageId: string) => {
      // Same rationale as apply: keep the proposal data so the card can
      // render its muted "Dismissed" state instead of disappearing.
      updateMessage(messageId, () => ({
        flowProposalStatus: "dismissed" as const,
      }));
    },
    [updateMessage],
  );

  const handleApprovePlan = useCallback(
    async (messageId: string) => {
      // Continue on the planning gate. The manual click path marks the
      // card "approved" (badge visible) and starts a fresh turn. The
      // skip-all auto-approve path reuses the SAME assistant message
      // slot (no second bubble) and skips the processing guard so the
      // bridge is invisible to the user.
      if (!lastModelRef.current) return;
      if (skipAllRef.current) {
        await handleSend(SKIP_ALL_APPROVAL_TEXT, lastModelRef.current, {
          silent: true,
          internal: true,
          reuseAssistantMessageId: messageId,
        });
        return;
      }
      updateMessage(messageId, () => ({
        planProposalStatus: "approved" as const,
      }));
      await handleSend(SKIP_ALL_APPROVAL_TEXT, lastModelRef.current);
    },
    [updateMessage, handleSend],
  );
  // Same trick as handleApplyFlowProposalRef — drained by onComplete.
  handleApprovePlanRef.current = handleApprovePlan;

  const handleAcknowledgeValidation = useCallback(
    (messageId: string) => {
      updateMessage(messageId, () => ({ validationAcknowledged: true }));
    },
    [updateMessage],
  );

  const handleDismissPlan = useCallback((messageId: string) => {
    // Dismiss transitions the card to "refining": the markdown stays on
    // the message (card keeps rendering) and is stashed so the user's
    // next handleSend re-injects it as prior-context for the agent.
    // The user is in control — we do NOT auto-send anything here.
    setMessages((prev) => {
      const target = prev.find((m) => m.id === messageId);
      const markdown = target?.pendingPlanProposal?.markdown ?? "";
      if (markdown) {
        dismissedPlanMarkdownRef.current = markdown;
      }
      return prev.map((m) =>
        m.id === messageId
          ? { ...m, planProposalStatus: "refining" as const }
          : m,
      );
    });
    setIsRefiningPlan(true);
  }, []);

  const toggleSkipAll = useCallback(() => {
    setSkipAll((prev) => {
      const next = !prev;
      skipAllRef.current = next;
      writeSkipAll(next);
      return next;
    });
  }, []);

  const handleResetPlan = useCallback(
    (messageId: string) => {
      // Reset closes the planning gate entirely. The stash is dropped so
      // the next handleSend does NOT re-inject the prior plan, and the
      // card flips to the muted "Dismissed" terminal state.
      dismissedPlanMarkdownRef.current = null;
      setIsRefiningPlan(false);
      updateMessage(messageId, () => ({
        planProposalStatus: "dismissed" as const,
      }));
    },
    [updateMessage],
  );

  const handleStopGeneration = useCallback(() => {
    abortControllerRef.current?.abort();

    setMessages((prev) =>
      prev.map((msg) =>
        msg.status === "streaming"
          ? {
              ...msg,
              status: "cancelled" as const,
              progress: undefined,
            }
          : msg,
      ),
    );
    setCurrentStep(null);
    setIsProcessing(false);
  }, []);

  const handleClearHistory = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setCurrentStep(null);
    setIsProcessing(false);
    dismissedPlanMarkdownRef.current = null;
    setIsRefiningPlan(false);
    const newId = `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`;
    sessionIdRef.current = newId;
    setSessionId(newId);
    // Wipe the user's session-scoped state on the backend so the
    // freshly-minted session starts from an empty registry overlay.
    void fireSessionReset(newId);
  }, []);

  const loadSession = useCallback((id: string, msgs: AssistantMessage[]) => {
    abortControllerRef.current?.abort();
    setMessages(msgs);
    setCurrentStep(null);
    setIsProcessing(false);
    dismissedPlanMarkdownRef.current = null;
    setIsRefiningPlan(false);
    sessionIdRef.current = id;
    setSessionId(id);
  }, []);

  return {
    messages,
    sessionId,
    isProcessing,
    currentStep,
    handleSend,
    handleApprove,
    handleUpdateFlowAction,
    handleApplyFlowProposal,
    handleDismissFlowProposal,
    handleApprovePlan,
    handleDismissPlan,
    handleResetPlan,
    handleAcknowledgeValidation,
    isRefiningPlan,
    skipAll,
    toggleSkipAll,
    handleRetry,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  };
}
