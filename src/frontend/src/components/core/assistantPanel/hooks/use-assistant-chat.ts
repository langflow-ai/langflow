import { useUpdateNodeInternals } from "@xyflow/react";
import { useCallback, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import {
  type AgenticFlowUpdateEvent,
  type AgenticStepType,
  postAssistStream,
} from "@/controllers/API/queries/agentic";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useAddComponent } from "@/hooks/use-add-component";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType } from "@/types/api";
import type {
  AssistantMessage,
  AssistantModel,
} from "../assistant-panel.types";

const uid = new ShortUniqueId();
const AGENTIC_SESSION_PREFIX = "agentic_";

interface UseAssistantChatReturn {
  messages: AssistantMessage[];
  sessionId: string;
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
  handleSend: (content: string, model: AssistantModel | null) => Promise<void>;
  handleApprove: (messageId: string, componentCode?: string) => Promise<void>;
  handleUpdateFlowAction: (
    messageId: string,
    actionId: string,
    status: "applied" | "dismissed",
  ) => void;
  handleApplyFlowProposal: (messageId: string) => void;
  handleDismissFlowProposal: (messageId: string) => void;
  handleApprovePlan: (messageId: string) => Promise<void>;
  handleDismissPlan: (messageId: string) => void;
  handleRetry: (messageId: string) => void;
  handleStopGeneration: () => void;
  handleClearHistory: () => void;
  loadSession: (id: string, msgs: AssistantMessage[]) => void;
}

export function useAssistantChat(): UseAssistantChatReturn {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<AgenticStepType | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastModelRef = useRef<AssistantModel | null>(null);
  // Per-send flag: once a `set_flow` event arrives, subsequent non-`edit_field`
  // events must be buffered too (defensive against mixed runs). Reset at the
  // start of every handleSend to avoid leaking state across requests.
  const proposalPendingRef = useRef<boolean>(false);
  const sessionIdRef = useRef<string>(
    `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`,
  );
  const [sessionId, setSessionId] = useState<string>(sessionIdRef.current);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const addComponent = useAddComponent();
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();
  // ReactFlow caches handle positions per node. When we mutate node data
  // that changes which handles are rendered or their position (e.g. flipping
  // _connectionMode on a ModelInput, switching selected_output, replacing a
  // node via set_flow), we MUST notify ReactFlow so existing edges find
  // their endpoints — otherwise the edge stays in state but renders as
  // disconnected.
  const updateNodeInternals = useUpdateNodeInternals();
  /** Apply a flow_update event to the canvas in real time */
  const applyFlowUpdate = useCallback((event: AgenticFlowUpdateEvent) => {
    switch (event.action) {
      case "set_flow": {
        const flow = event.flow as {
          data?: { nodes?: unknown[]; edges?: unknown[] };
        };
        if (flow?.data?.nodes) {
          const setNodes = useFlowStore.getState().setNodes;
          const setEdges = useFlowStore.getState().setEdges;
          setNodes(flow.data.nodes as never[]);
          setEdges((flow.data.edges ?? []) as never[]);
        }
        break;
      }
      case "add_component": {
        const node = event.node as Record<string, unknown>;
        if (node) {
          const setNodes = useFlowStore.getState().setNodes;
          setNodes((prev) => [...prev, node as never]);
        }
        break;
      }
      case "connect": {
        const edge = event.edge as Record<string, unknown>;
        if (edge) {
          const setEdges = useFlowStore.getState().setEdges;
          setEdges((prev) => [...prev, edge as never]);
          // Refresh both endpoints so ReactFlow reconciles handle positions
          // and renders the new edge between them.
          const src = edge.source as string | undefined;
          const tgt = edge.target as string | undefined;
          if (src) updateNodeInternals(src);
          if (tgt) updateNodeInternals(tgt);
        }
        break;
      }
      case "remove_component": {
        const nodeId = event.component_id as string;
        if (nodeId) {
          const setNodes = useFlowStore.getState().setNodes;
          const setEdges = useFlowStore.getState().setEdges;
          setNodes((prev) =>
            prev.filter((n) => (n as Record<string, unknown>).id !== nodeId),
          );
          setEdges((prev) =>
            prev.filter((e) => {
              const edge = e as Record<string, unknown>;
              return edge.source !== nodeId && edge.target !== nodeId;
            }),
          );
        }
        break;
      }
      case "configure": {
        const compId = event.component_id as string;
        const params = event.params as Record<string, unknown>;
        if (compId && params) {
          const setNodes = useFlowStore.getState().setNodes;
          setNodes((prev) =>
            prev.map((n) => {
              const node = n as Record<string, unknown>;
              if (node.id !== compId) return n;
              const data = node.data as Record<string, unknown>;
              const innerNode = (data?.node ?? {}) as Record<string, unknown>;
              const tpl = (innerNode?.template ?? {}) as Record<
                string,
                unknown
              >;
              return {
                ...node,
                data: {
                  ...data,
                  node: {
                    ...innerNode,
                    template: {
                      ...tpl,
                      ...Object.fromEntries(
                        Object.entries(params).map(([k, v]) => [
                          k,
                          {
                            ...(tpl[k] as Record<string, unknown>),
                            value: v,
                          },
                        ]),
                      ),
                    },
                  },
                },
              } as never;
            }),
          );
        }
        break;
      }
      case "select_output": {
        // The frontend's GenericNode reads `data.selected_output` (top-level
        // on the ReactFlow node data, NOT inside data.node) to decide which
        // output's handle to render and which label to show in the
        // dropdown. Patch at the same level so OpenAIModel switches from
        // "Model Response" to "Language Model" when wired via model_output.
        const compId = event.component_id as string;
        const outputName = event.output_name as string;
        if (compId && outputName) {
          const setNodes = useFlowStore.getState().setNodes;
          setNodes((prev) =>
            prev.map((n) => {
              const node = n as Record<string, unknown>;
              if (node.id !== compId) return n;
              const data = (node.data ?? {}) as Record<string, unknown>;
              return {
                ...node,
                data: {
                  ...data,
                  selected_output: outputName,
                },
              } as never;
            }),
          );
          // The selected output's handle is the only one rendered for nodes
          // with multiple outputs, so the handle position changes when we
          // switch which output is "active" — refresh ReactFlow's cache.
          updateNodeInternals(compId);
        }
        break;
      }
      case "set_connection_mode": {
        // ModelInput dropdown reads `data._connectionMode` to switch from
        // its inline model picker to "Connect other models" mode (which
        // exposes the left handle for an external model edge). Mirror the
        // backend flip so the connected edge actually renders.
        const compId = event.component_id as string;
        const enabled = event.enabled as boolean;
        if (compId !== undefined) {
          const setNodes = useFlowStore.getState().setNodes;
          setNodes((prev) =>
            prev.map((n) => {
              const node = n as Record<string, unknown>;
              if (node.id !== compId) return n;
              const data = (node.data ?? {}) as Record<string, unknown>;
              return {
                ...node,
                data: {
                  ...data,
                  _connectionMode: enabled,
                },
              } as never;
            }),
          );
          // Toggling _connectionMode swaps the model field's UI between an
          // inline dropdown and a connection handle. The handle's DOM
          // position changes — without this notification ReactFlow keeps
          // the cached position and the edge can't find its target.
          updateNodeInternals(compId);
        }
        break;
      }
      default:
        break;
    }
  }, []);

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
    async (content: string, model: AssistantModel | null) => {
      if (isProcessing) return;

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

      const assistantMessageId = uid.randomUUID(10);
      const assistantMessage: AssistantMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "streaming",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsProcessing(true);
      proposalPendingRef.current = false;

      abortControllerRef.current = new AbortController();

      const completedSteps: AgenticStepType[] = [];
      let currentStepTracked: AgenticStepType | null = null;

      try {
        await postAssistStream(
          {
            flow_id: currentFlowId || "",
            input_value: content,
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
                const markdown =
                  typeof event.markdown === "string" ? event.markdown : "";
                updateMessage(assistantMessageId, () => ({
                  pendingPlanProposal: { markdown },
                  planProposalStatus: "pending" as const,
                }));
                return;
              }
              if (event.action === "set_flow") {
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
              updateMessage(assistantMessageId, () => ({
                status: "complete" as const,
                content: event.data.result || "",
                result: {
                  content: event.data.result || "",
                  validated: event.data.validated,
                  hasFlow: event.data.has_flow,
                  className: event.data.class_name,
                  componentCode: event.data.component_code,
                  validationAttempts: event.data.validation_attempts,
                  validationError: event.data.validation_error,
                },
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
            error: "Failed to connect to assistant",
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
    (messageId: string, actionId: string, status: "applied" | "dismissed") => {
      updateMessage(messageId, (msg) => ({
        flowActions: msg.flowActions?.map((a) =>
          a.id === actionId ? { ...a, status } : a,
        ),
      }));
    },
    [updateMessage],
  );

  const handleApplyFlowProposal = useCallback(
    (messageId: string) => {
      const message = messages.find((m) => m.id === messageId);
      const proposal = message?.pendingFlowProposal;
      if (!proposal) return;

      // Replay the gating set_flow first, then any tail edits in order.
      applyFlowUpdate({
        event: "flow_update",
        action: "set_flow",
        flow: proposal.flow,
      });
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
      // Continue on the planning gate. Mark the card as approved (the user
      // sees a muted "Plan approved" badge), then send a fresh user turn so
      // the agent resumes from where it stopped after propose_plan. The
      // approval signal is plain text — the agent's prompt teaches it that
      // an approval message means "now run search/describe/build_flow".
      updateMessage(messageId, () => ({
        planProposalStatus: "approved" as const,
      }));
      if (!lastModelRef.current) return;
      await handleSend(
        "User approved the plan. Proceed with the build.",
        lastModelRef.current,
      );
    },
    [updateMessage, handleSend],
  );

  const handleDismissPlan = useCallback(
    (messageId: string) => {
      // Dismiss leaves the chat open. The user types refinement feedback
      // (e.g. "use Claude instead of GPT") as a regular message; the agent
      // sees it and re-calls propose_plan with a revised plan. We do NOT
      // auto-send anything here — the user is in control.
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
    const newId = `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`;
    sessionIdRef.current = newId;
    setSessionId(newId);
  }, []);

  const loadSession = useCallback((id: string, msgs: AssistantMessage[]) => {
    abortControllerRef.current?.abort();
    setMessages(msgs);
    setCurrentStep(null);
    setIsProcessing(false);
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
    handleRetry,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  };
}
