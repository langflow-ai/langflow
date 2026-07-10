import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep } from "lodash";
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
import { commandAckMessages } from "./command-ack";
import { applyFlowProposalToCanvas } from "../helpers/apply-flow-proposal";
import { applyFlowUpdate as applyFlowUpdateImpl } from "../helpers/apply-flow-update";
import {
  buildRefinementInput,
  buildTaskFromEvent,
  inProgressTaskFromEvent,
} from "../helpers/assistant-event-mappers";
import {
  parseHistoryCommand,
  readHistoryLimit,
  writeHistoryLimit,
} from "./history-storage";
import {
  parseIterationsCommand,
  readIterationsLimit,
  writeIterationsLimit,
} from "./iterations-storage";
import { readSkipAll, writeSkipAll } from "./skip-all-storage";
import type { UseAssistantChatReturn } from "./use-assistant-chat.types";

const uid = new ShortUniqueId();
const AGENTIC_SESSION_PREFIX = "agentic_";
const SKIP_ALL_COMMAND = "/skip-all";
const SKIP_ALL_APPROVAL_TEXT =
  "User approved the plan. Proceed with the build.";
// Backend protocol string (never user-authored) — the silent continuation turn after
// an applied edit; must stay byte-identical to EDIT_CONTINUATION_INPUT in flow_types.py.
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

// Known size debt: `handleSend` (~390 lines, the SSE pump) keeps this hook over
// the ceiling; splitting it needs a dedicated state-machine refactor.
export function useAssistantChat(): UseAssistantChatReturn {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<AgenticStepType | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastModelRef = useRef<AssistantModel | null>(null);
  // After a set_flow, buffer subsequent events (mixed-run defense); reset per send.
  const proposalPendingRef = useRef<boolean>(false);
  // Last dismissed-not-reset plan markdown, re-injected as context by next send.
  const dismissedPlanMarkdownRef = useRef<string | null>(null);
  const [isRefiningPlan, setIsRefiningPlan] = useState<boolean>(false);
  // localStorage-backed; the ref keeps the latest value visible to closures.
  const [skipAll, setSkipAll] = useState<boolean>(() => readSkipAll());
  const skipAllRef = useRef<boolean>(skipAll);
  skipAllRef.current = skipAll;
  // `/history N` memory window; null = backend defaults. Ref for same-tick reads.
  const historyLimitRef = useRef<number | null>(readHistoryLimit());
  // `/iterations N` step budget; null = backend default (30). Ref for same-tick reads.
  const iterationsLimitRef = useRef<number | null>(readIterationsLimit());
  // Auto-approve queue: a ref so handlers see the value in the same tick.
  const autoApprovePlanRef = useRef<string | null>(null);
  // Lazy ref: a direct handleSend dep on handleApprovePlan would be circular.
  const handleApprovePlanRef = useRef<((id: string) => Promise<void>) | null>(
    null,
  );
  const sessionIdRef = useRef<string>(
    `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`,
  );
  const [sessionId, setSessionId] = useState<string>(sessionIdRef.current);

  // WS-3 / RC-3: components are session-scoped; only New session wipes them.

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const addComponent = useAddComponent();
  const saveFlow = useSaveFlow();
  // Ids whose continuation already fired; a ref for synchronous visibility.
  const continuedEditMsgIds = useRef<Set<string>>(new Set());
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();
  // ReactFlow caches handle positions; un-notified mutations disconnect edges.
  const updateNodeInternals = useUpdateNodeInternals();
  // Pure-helper delegation; deps rely on xyflow's stable updateNodeInternals.
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
      // ``internal`` bypasses the processing guard to avoid the unmount blink.
      if (!options?.internal && isProcessing) return;
      // ``silent`` hides the user message; ``reuseAssistantMessageId`` resets a slot.
      const silent = options?.silent === true;
      const reuseId = options?.reuseAssistantMessageId;

      // Exact match only: "/skip-all please" is a real prompt for the backend.
      if (content.trim() === SKIP_ALL_COMMAND) {
        const next = !skipAllRef.current;
        skipAllRef.current = next;
        setSkipAll(next);
        writeSkipAll(next);
        const announcement = next
          ? "Skip-all mode enabled. Plans, flow proposals, and validated components will be approved automatically."
          : "Skip-all mode disabled. Plans, flow proposals, and validated components will wait for your Continue click.";
        setMessages((prev) => [
          ...prev,
          ...commandAckMessages(content, announcement),
        ]);
        return;
      }

      // `/history N` sets the memory window; local command, never sent.
      const historyCmd = parseHistoryCommand(content, historyLimitRef.current);
      if (historyCmd) {
        if (historyCmd.changed) {
          historyLimitRef.current = historyCmd.limit;
          writeHistoryLimit(historyCmd.limit);
        }
        setMessages((prev) => [
          ...prev,
          ...commandAckMessages(content, historyCmd.announcement),
        ]);
        return;
      }

      // `/iterations N` sets the Agent step budget; local command, never sent.
      const iterationsCmd = parseIterationsCommand(
        content,
        iterationsLimitRef.current,
      );
      if (iterationsCmd) {
        if (iterationsCmd.changed) {
          iterationsLimitRef.current = iterationsCmd.limit;
          writeIterationsLimit(iterationsCmd.limit);
        }
        setMessages((prev) => [
          ...prev,
          ...commandAckMessages(content, iterationsCmd.announcement),
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
        // Reset the slot in place ("streaming" keeps the loader mounted);
        // clearing inProgressTask/reverted stops a prior turn bleeding in.
        updateMessage(reuseId, () => ({
          content: "",
          status: "streaming" as const,
          progress: undefined,
          error: undefined,
          pendingPlanProposal: undefined,
          planProposalStatus: undefined,
          inProgressTask: undefined,
          reverted: undefined,
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

      // Re-inject the dismissed plan — the LLM has no server-side history.
      const stashedPlan = dismissedPlanMarkdownRef.current;
      const inputValue = stashedPlan
        ? buildRefinementInput(stashedPlan, content)
        : content;

      // Abort in-flight streams: a leaked SSE reader would mutate the same message.
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
            history_limit: historyLimitRef.current ?? undefined,
            iterations_limit: iterationsLimitRef.current ?? undefined,
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
                // A retry restarts generation; stale partial output must not linger.
                ...(event.step === "retrying" ? { content: "" } : {}),
                progress: {
                  step: event.step,
                  attempt: event.attempt,
                  maxAttempts: event.max_attempts,
                  message: event.message,
                  error: event.error,
                  // Preserve componentCode/className when the new event omits them
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
              // Tool result delivered — retire the in-progress spinner row.
              updateMessage(assistantMessageId, () => ({
                inProgressTask: undefined,
              }));
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
                // Planning gate: canvas untouched; a fresh plan supersedes the stash.
                dismissedPlanMarkdownRef.current = null;
                setIsRefiningPlan(false);
                if (skipAllRef.current) {
                  // Skip-all: queue auto-approve and clear the streamed preamble.
                  autoApprovePlanRef.current = assistantMessageId;
                  updateMessage(assistantMessageId, () => ({
                    content: "",
                    inProgressTask: undefined,
                  }));
                  return;
                }
                const markdown =
                  typeof event.markdown === "string" ? event.markdown : "";
                // Clear inProgressTask: the agent is only planning, so no build
                // spinner must linger next to the plan card.
                updateMessage(assistantMessageId, () => ({
                  pendingPlanProposal: { markdown },
                  planProposalStatus: "pending" as const,
                  inProgressTask: undefined,
                }));
                return;
              }
              if (event.action === "set_flow") {
                if (skipAllRef.current || event.auto_apply === true) {
                  // Direct apply — the queue-and-drain approach hit a stale-closure race.
                  applyFlowUpdate({
                    event: "flow_update",
                    action: "set_flow",
                    flow: event.flow,
                  });
                  return;
                }
                // Buffer as a proposal; canvas untouched until the user applies it.
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
              // Proposal pending: buffer later events to avoid partial canvas state.
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
              // Checklist entry; dedup so SSE replays don't duplicate rows.
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
            onToolStart: (event) => {
              // Latest tool_start wins; matching flow_update (or run end) retires it.
              updateMessage(assistantMessageId, () => ({
                inProgressTask: inProgressTaskFromEvent(event),
              }));
            },
            onFileWritten: (event) => {
              // One WrittenFile entry per successful write/edit, in arrival order.
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
                // Chain into turn 2 without resetting state (avoids the UI blink).
                autoApprovePlanRef.current = null;
                setTimeout(() => {
                  handleApprovePlanRef.current?.(planMsgId);
                }, 0);
                return;
              }
              updateMessage(assistantMessageId, () => ({
                status: "complete" as const,
                inProgressTask: undefined,
                content: event.data.result || "",
                // Pure edits stay false so approval doesn't spawn a second message.
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
                // Kept on the message for reopen; duration in ms for MessageMetadata.
                usage: event.data.usage,
                duration:
                  typeof event.data.duration_seconds === "number"
                    ? event.data.duration_seconds * 1000
                    : undefined,
                restoreVersionId: event.data.restore_version_id,
                notices: event.data.notices,
              }));
              setCurrentStep(null);
              setIsProcessing(false);
            },
            onError: (event) => {
              updateMessage(assistantMessageId, () => ({
                status: "error" as const,
                error: event.message,
                errorDetail: event.detail,
              }));
              setCurrentStep(null);
              setIsProcessing(false);
            },
            onCancelled: () => {
              updateMessage(assistantMessageId, () => ({
                status: "cancelled" as const,
                progress: undefined,
                inProgressTask: undefined,
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

      // All resolved with >=1 applied: save (backend reads DB) then resume.
      const msg = messages.find((m) => m.id === messageId);
      const actions = (msg?.flowActions ?? []).map((a) =>
        a.id === actionId ? { ...a, status } : a,
      );
      if (actions.length === 0) return;
      const stillPending = actions.some((a) => a.status === "pending");
      const anyApplied = actions.some((a) => a.status === "applied");
      if (stillPending || !anyApplied) return;
      // A pure edit (no deferred "...and run it" step) must NOT spawn a
      // second assistant message — the backend computes this flag.
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

      // Snapshot the canvas BEFORE mutating so Revert can restore this exact
      // state and re-enable the Add/Replace actions (client-side undo).
      const preApply = useFlowStore.getState();
      const snapshot = {
        nodes: cloneDeep(preApply.nodes) as unknown[],
        edges: cloneDeep(preApply.edges) as unknown[],
      };

      applyFlowProposalToCanvas(proposal, mode, updateNodeInternals);

      // Confirm ("Added to canvas"), then re-enable Add/Replace after 3s while
      // keeping the snapshot so the last apply stays undoable via the pending card.
      updateMessage(messageId, () => ({
        flowProposalStatus: "applied" as const,
        flowProposalSnapshot: snapshot,
        reverted: false,
      }));
      setTimeout(() => {
        updateMessage(messageId, (msg) =>
          msg.flowProposalStatus === "applied"
            ? { flowProposalStatus: "pending" }
            : {},
        );
      }, 3000);
    },
    [messages, updateMessage, updateNodeInternals],
  );

  const handleRevertFlowProposal = useCallback(
    (messageId: string) => {
      const message = messages.find((m) => m.id === messageId);
      const snapshot = message?.flowProposalSnapshot;
      if (!snapshot) return;
      // Restore atomically (same path as apply so loop/dynamic edges redraw) and
      // clear the snapshot so the card returns to the initial pending state.
      useFlowStore
        .getState()
        .setNodesAndEdges(snapshot.nodes as never[], snapshot.edges as never[]);
      updateMessage(messageId, () => ({
        flowProposalStatus: "pending" as const,
        flowProposalSnapshot: undefined,
      }));
    },
    [messages, updateMessage],
  );

  const handleDismissFlowProposal = useCallback(
    (messageId: string) => {
      // Keep the proposal data so the card renders muted instead of vanishing.
      updateMessage(messageId, () => ({
        flowProposalStatus: "dismissed" as const,
      }));
    },
    [updateMessage],
  );

  const handleApprovePlan = useCallback(
    async (messageId: string) => {
      // Manual click marks the card approved + fresh turn; skip-all reuses
      // the SAME message slot so the auto-approve bridge is invisible.
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

  const handleMarkReverted = useCallback(
    (messageId: string) => {
      updateMessage(messageId, () => ({ reverted: true }));
    },
    [updateMessage],
  );

  const handleDismissPlan = useCallback((messageId: string) => {
    // Dismiss = "refining": stash the markdown for re-injection on the next
    // handleSend; the user stays in control (nothing auto-sends here).
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
      // Reset closes the gate: drop the stash (no re-injection) and flip
      // the card to the muted "Dismissed" terminal state.
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
    handleRevertFlowProposal,
    handleDismissFlowProposal,
    handleApprovePlan,
    handleDismissPlan,
    handleResetPlan,
    handleAcknowledgeValidation,
    isRefiningPlan,
    skipAll,
    toggleSkipAll,
    handleRetry,
    handleMarkReverted,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  };
}
