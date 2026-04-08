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
  const sessionIdRef = useRef<string>(
    `${AGENTIC_SESSION_PREFIX}${uid.randomUUID(16)}`,
  );
  const [sessionId, setSessionId] = useState<string>(sessionIdRef.current);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const addComponent = useAddComponent();
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();
  const paste = useFlowStore((state) => state.paste);

  /** Apply a flow_update event to the canvas in real time */
  const applyFlowUpdate = useCallback(
    (event: AgenticFlowUpdateEvent) => {
      switch (event.action) {
        case "set_flow": {
          const flow = event.flow as {
            data?: { nodes?: unknown[]; edges?: unknown[] };
          };
          if (flow?.data?.nodes) {
            paste(
              {
                nodes: flow.data.nodes as never[],
                edges: (flow.data.edges ?? []) as never[],
              },
              { x: 100, y: 100 },
            );
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
        default:
          break;
      }
    },
    [paste],
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
              } else {
                applyFlowUpdate(event);
              }
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
    handleRetry,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  };
}
