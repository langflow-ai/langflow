import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import {
  type DeploymentExecutionResponse,
  useGetDeploymentExecutionById,
  usePostCreateDeploymentExecution,
} from "@/controllers/API/queries/deployments/use-deployments";
import { WatsonxOrchestrateIcon } from "@/icons/IBM";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  toolTraces?: ToolTrace[];
};

type ToolTrace = {
  kind: "tool_call" | "tool_response";
  toolName: string;
  toolCallId?: string;
  args?: unknown;
  content?: string;
};

type ToolDetailGroup = {
  key: string;
  toolName: string;
  input?: unknown;
  output?: unknown;
};

type TestAgentModalProps = {
  open: boolean;
  providerId: string;
  providerKey?: string;
  deploymentId: string;
  deploymentType: "agent" | "mcp";
  deploymentMode?: string | null;
  deploymentName: string;
  onOpenChange: (open: boolean) => void;
};

export const TestAgentModal = ({
  open,
  providerId,
  providerKey,
  deploymentId,
  deploymentType,
  deploymentMode,
  deploymentName,
  onOpenChange,
}: TestAgentModalProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isResponding, setIsResponding] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [expandedToolDetails, setExpandedToolDetails] = useState<
    Record<string, boolean>
  >({});
  const [copiedToolDetailKey, setCopiedToolDetailKey] = useState<string | null>(
    null,
  );
  const activePollTokenRef = useRef(0);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const copiedToolDetailTimerRef = useRef<number | null>(null);
  const createExecutionMutation = usePostCreateDeploymentExecution();
  const getExecutionStatusMutation = useGetDeploymentExecutionById({
    providerId,
  });
  const isWatsonxProvider = providerKey === "watsonx-orchestrate";
  const isWatsonxExecutionResponse = (
    response: DeploymentExecutionResponse,
  ): boolean => {
    if (isWatsonxProvider) {
      return true;
    }
    const outputObject = getWatsonxOutputObject(response);
    if (!outputObject) {
      return false;
    }
    const data = outputObject.data as Record<string, unknown> | undefined;
    const message = data?.message as Record<string, unknown> | undefined;
    const content = message?.content;
    return (
      Array.isArray(content) &&
      content.some(
        (item) =>
          item &&
          typeof item === "object" &&
          (typeof (item as Record<string, unknown>).text === "string" ||
            typeof (item as Record<string, unknown>).response_type ===
              "string"),
      )
    );
  };

  const getWatsonxOutputObject = (
    response: DeploymentExecutionResponse,
  ): Record<string, unknown> | null => {
    const outputCandidate = (() => {
      if (response.output !== undefined && response.output !== null) {
        return response.output;
      }
      if (
        response.provider_result &&
        typeof response.provider_result === "object"
      ) {
        const providerResult = response.provider_result as Record<
          string,
          unknown
        >;
        if (
          providerResult.output !== undefined &&
          providerResult.output !== null
        ) {
          return providerResult.output;
        }
        if (
          providerResult.result !== undefined &&
          providerResult.result !== null
        ) {
          return providerResult.result;
        }
      }
      return null;
    })();

    if (!outputCandidate) {
      return null;
    }
    if (typeof outputCandidate === "object") {
      return outputCandidate as Record<string, unknown>;
    }
    if (typeof outputCandidate === "string") {
      const trimmed = outputCandidate.trim();
      if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
        return null;
      }
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === "object") {
          return parsed as Record<string, unknown>;
        }
      } catch {
        return null;
      }
    }
    return null;
  };

  const extractWatsonxAssistantText = (
    outputObject: Record<string, unknown> | null,
  ): string | null => {
    if (!outputObject) {
      return null;
    }
    const data = outputObject.data as Record<string, unknown> | undefined;
    const message = data?.message as Record<string, unknown> | undefined;
    const content = message?.content;
    if (!Array.isArray(content)) {
      return null;
    }
    const textEntry = content.find(
      (item) =>
        item &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).text === "string" &&
        (item as Record<string, unknown>).text?.toString().trim(),
    ) as Record<string, unknown> | undefined;
    const text = textEntry?.text;
    return typeof text === "string" && text.trim() ? text.trim() : null;
  };

  const buildAssistantReplyFromExecution = (
    response: DeploymentExecutionResponse,
  ): string => {
    if (isWatsonxExecutionResponse(response)) {
      const watsonxOutput = getWatsonxOutputObject(response);
      const assistantText = extractWatsonxAssistantText(watsonxOutput);
      if (assistantText) {
        return assistantText;
      }
    }

    const executionOutput = (() => {
      if (response.output !== undefined && response.output !== null) {
        return response.output;
      }
      if (
        response.provider_result &&
        typeof response.provider_result === "object"
      ) {
        const providerResult = response.provider_result as Record<
          string,
          unknown
        >;
        return providerResult.output ?? providerResult.result ?? null;
      }
      return null;
    })();
    if (typeof executionOutput === "string" && executionOutput.trim()) {
      return executionOutput;
    }
    if (executionOutput && typeof executionOutput === "object") {
      return JSON.stringify(executionOutput, null, 2);
    }

    if (!isWatsonxExecutionResponse(response)) {
      return response.status
        ? `Execution status: ${response.status}.`
        : "Execution accepted by deployment provider.";
    }

    const providerResult = response.provider_result || {};
    const runId = providerResult.run_id;
    const taskId = providerResult.task_id;
    const messageId = providerResult.message_id;
    const nextThreadId = providerResult.thread_id;

    return [
      "Execution accepted by deployment provider.",
      runId ? `Run ID: ${String(runId)}` : null,
      taskId ? `Task ID: ${String(taskId)}` : null,
      messageId ? `Message ID: ${String(messageId)}` : null,
      nextThreadId ? `Thread ID: ${String(nextThreadId)}` : null,
    ]
      .filter(Boolean)
      .join("\n");
  };

  const extractToolTraces = (
    response: DeploymentExecutionResponse,
  ): ToolTrace[] => {
    if (!isWatsonxExecutionResponse(response)) {
      return [];
    }
    const output = getWatsonxOutputObject(response);
    if (!output) {
      return [];
    }
    const data = output.data as Record<string, unknown> | undefined;
    const message = data?.message as Record<string, unknown> | undefined;
    const stepHistory = message?.step_history;
    if (!Array.isArray(stepHistory)) {
      return [];
    }

    const traces: ToolTrace[] = [];
    const parsePossibleJsonString = (value: unknown): unknown => {
      if (typeof value !== "string") {
        return value;
      }
      const trimmed = value.trim();
      if (!trimmed) {
        return "";
      }
      if (
        (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
        (trimmed.startsWith("[") && trimmed.endsWith("]"))
      ) {
        try {
          return JSON.parse(trimmed);
        } catch {
          return value;
        }
      }
      return value;
    };
    const formatToolContent = (value: unknown): string => {
      if (value == null) {
        return "";
      }
      if (typeof value === "string") {
        const trimmed = value.trim();
        if (!trimmed) {
          return "";
        }
        const parsed = parsePossibleJsonString(trimmed);
        if (parsed !== trimmed) {
          return formatToolContent(parsed);
        }
        return trimmed;
      }
      if (Array.isArray(value)) {
        const chunks = value
          .map((item) => formatToolContent(item))
          .filter((item) => item.trim().length > 0);
        if (chunks.length > 0) {
          return chunks.join("\n\n");
        }
        try {
          return JSON.stringify(value, null, 2);
        } catch {
          return "";
        }
      }
      if (typeof value === "object") {
        const objectValue = value as Record<string, unknown>;
        for (const key of ["text", "content", "result", "output"]) {
          if (key in objectValue) {
            const extracted = formatToolContent(objectValue[key]);
            if (extracted.trim()) {
              return extracted;
            }
          }
        }
        try {
          return JSON.stringify(objectValue, null, 2);
        } catch {
          return "";
        }
      }
      return String(value);
    };
    const buildTraceKey = (trace: ToolTrace): string => {
      if (trace.kind === "tool_call") {
        if (trace.toolCallId) {
          return `tool_call:${trace.toolCallId}`;
        }
        return `tool_call:${trace.toolName}:${JSON.stringify(trace.args ?? null)}`;
      }
      if (trace.toolCallId) {
        return `tool_response:${trace.toolCallId}`;
      }
      return `tool_response:${trace.toolName}:${trace.content ?? ""}`;
    };
    for (const step of stepHistory) {
      if (!step || typeof step !== "object") {
        continue;
      }
      const stepDetails = (step as { step_details?: unknown }).step_details;
      if (!Array.isArray(stepDetails)) {
        continue;
      }
      for (const detail of stepDetails) {
        if (!detail || typeof detail !== "object") {
          continue;
        }
        const typedDetail = detail as Record<string, unknown>;
        const type = typedDetail.type;

        if (type === "tool_calls" && Array.isArray(typedDetail.tool_calls)) {
          for (const toolCall of typedDetail.tool_calls) {
            if (!toolCall || typeof toolCall !== "object") {
              continue;
            }
            const typedToolCall = toolCall as Record<string, unknown>;
            traces.push({
              kind: "tool_call",
              toolName: String(
                typedToolCall.name || typedToolCall.tool_name || "Unknown Tool",
              ),
              toolCallId:
                typeof typedToolCall.id === "string"
                  ? typedToolCall.id
                  : undefined,
              args: parsePossibleJsonString(typedToolCall.args ?? null),
            });
          }
          continue;
        }

        if (type === "tool_call") {
          traces.push({
            kind: "tool_call",
            toolName: String(
              typedDetail.name || typedDetail.tool_name || "Unknown Tool",
            ),
            toolCallId:
              typeof typedDetail.tool_call_id === "string"
                ? typedDetail.tool_call_id
                : undefined,
            args: parsePossibleJsonString(typedDetail.args ?? null),
          });
          continue;
        }

        if (type === "tool_response") {
          traces.push({
            kind: "tool_response",
            toolName: String(
              typedDetail.name || typedDetail.tool_name || "Unknown Tool",
            ),
            toolCallId:
              typeof typedDetail.tool_call_id === "string"
                ? typedDetail.tool_call_id
                : undefined,
            content: formatToolContent(typedDetail.content),
          });
        }
      }
    }

    const uniqueTraces: ToolTrace[] = [];
    const seenTraceKeys = new Set<string>();
    for (const trace of traces) {
      const key = buildTraceKey(trace);
      if (seenTraceKeys.has(key)) {
        continue;
      }
      seenTraceKeys.add(key);
      uniqueTraces.push(trace);
    }

    return uniqueTraces
      .map((trace, index) => ({ trace, index }))
      .sort((a, b) => {
        const aId = a.trace.toolCallId;
        const bId = b.trace.toolCallId;

        if (aId && bId && aId === bId && a.trace.kind !== b.trace.kind) {
          return a.trace.kind === "tool_call" ? -1 : 1;
        }

        return a.index - b.index;
      })
      .map(({ trace }) => trace);
  };

  const sleep = (ms: number) =>
    new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });

  const isCompletedStatus = (statusValue?: string | null): boolean => {
    const normalized = (statusValue || "").toLowerCase();
    return normalized === "completed" || normalized === "success";
  };

  const isFailedStatus = (statusValue?: string | null): boolean => {
    const normalized = (statusValue || "").toLowerCase();
    return normalized === "failed" || normalized === "error";
  };
  const normalizedMode = (deploymentMode || "").trim().toLowerCase();
  const showWatsonxModeBadge = isWatsonxProvider && Boolean(normalizedMode);
  const modeBadgeLabel =
    normalizedMode === "live"
      ? "Live"
      : normalizedMode === "draft"
        ? "Draft"
        : null;
  const modeBadgeClass =
    normalizedMode === "live"
      ? "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
      : "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400";
  const modeLabelForMeta =
    normalizedMode === "live"
      ? "Live"
      : normalizedMode === "draft"
        ? "Draft"
        : null;
  const providerLabel = isWatsonxProvider
    ? "watsonx Orchestrate"
    : "Deployment";

  const valueToMultilineText = (value: unknown): string => {
    if (value === undefined || value === null) {
      return "";
    }
    if (typeof value === "string") {
      return value.trim();
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  };

  const toolOutputIndicatesError = (output: unknown): boolean => {
    const outputText = valueToMultilineText(output).toLowerCase();
    if (!outputText) {
      return false;
    }
    return /(error|failed|exception|traceback|timed out|invalid|no result)/i.test(
      outputText,
    );
  };

  const extractToolErrorSummary = (output: unknown): string | null => {
    const outputText = valueToMultilineText(output);
    if (!outputText) {
      return null;
    }
    const firstMatchingLine = outputText
      .split("\n")
      .map((line) => line.trim())
      .find((line) =>
        /(error|failed|exception|traceback|invalid|no result)/i.test(line),
      );
    if (!firstMatchingLine) {
      return null;
    }
    return firstMatchingLine.length > 180
      ? `${firstMatchingLine.slice(0, 177)}...`
      : firstMatchingLine;
  };

  const copyToolDetail = async (value: unknown, key: string): Promise<void> => {
    const text = valueToMultilineText(value);
    if (!text) {
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopiedToolDetailKey(key);
      if (copiedToolDetailTimerRef.current) {
        window.clearTimeout(copiedToolDetailTimerRef.current);
      }
      copiedToolDetailTimerRef.current = window.setTimeout(() => {
        setCopiedToolDetailKey((current) => (current === key ? null : current));
      }, 1800);
    } catch {
      // Clipboard may be unavailable in some environments; no-op.
    }
  };

  const resizeComposer = (): void => {
    const textarea = composerRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 40), 144);
    textarea.style.height = `${nextHeight}px`;
  };

  const groupToolTraces = (toolTraces: ToolTrace[]): ToolDetailGroup[] => {
    const grouped = new Map<string, ToolDetailGroup>();
    const orderedKeys: string[] = [];

    toolTraces.forEach((trace, index) => {
      const key = trace.toolCallId?.trim()
        ? trace.toolCallId
        : `${trace.toolName}-${index}`;

      if (!grouped.has(key)) {
        grouped.set(key, {
          key,
          toolName: trace.toolName,
        });
        orderedKeys.push(key);
      }

      const existing = grouped.get(key);
      if (!existing) {
        return;
      }

      if (
        existing.toolName === "Unknown Tool" &&
        trace.toolName !== "Unknown Tool"
      ) {
        existing.toolName = trace.toolName;
      }

      if (
        trace.kind === "tool_call" &&
        trace.args !== undefined &&
        trace.args !== null
      ) {
        existing.input = trace.args;
      }
      if (trace.kind === "tool_response" && trace.content !== undefined) {
        existing.output = trace.content;
      }
    });

    return orderedKeys
      .map((key) => grouped.get(key))
      .filter((group): group is ToolDetailGroup => Boolean(group));
  };

  const toHighlightedSnippet = (
    value: unknown,
  ): { language: string; code: string } | null => {
    if (value === undefined || value === null) {
      return null;
    }

    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) {
        return null;
      }
      if (
        (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
        (trimmed.startsWith("[") && trimmed.endsWith("]"))
      ) {
        try {
          return {
            language: "json",
            code: JSON.stringify(JSON.parse(trimmed), null, 2),
          };
        } catch {
          // Fall through to string representation.
        }
      }
      return { language: "json", code: JSON.stringify(trimmed, null, 2) };
    }

    try {
      return { language: "json", code: JSON.stringify(value, null, 2) };
    } catch {
      return { language: "json", code: JSON.stringify(String(value), null, 2) };
    }
  };

  useEffect(() => {
    if (!open) {
      activePollTokenRef.current += 1;
      setDraft("");
      setIsResponding(false);
      setThreadId(null);
      setMessages([]);
      setExpandedToolDetails({});
      setCopiedToolDetailKey(null);
    }
  }, [open]);

  useEffect(() => {
    resizeComposer();
  }, [draft, open]);

  useEffect(() => {
    return () => {
      if (copiedToolDetailTimerRef.current) {
        window.clearTimeout(copiedToolDetailTimerRef.current);
      }
    };
  }, []);

  const handleSend = async () => {
    const prompt = draft.trim();
    if (!prompt || isResponding) {
      return;
    }
    if (!providerId.trim() || !deploymentId.trim()) {
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content:
            "Missing deployment context for execution. Re-open this modal from a deployment row and try again.",
        },
      ]);
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: prompt,
    };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setIsResponding(true);

    try {
      const initialResponse = await createExecutionMutation.mutateAsync({
        provider_id: providerId,
        deployment_id: deploymentId,
        provider_data: {
          input: prompt,
          ...(isWatsonxProvider && threadId ? { thread_id: threadId } : {}),
        },
      });

      const providerResult = initialResponse.provider_result || {};
      if (
        isWatsonxProvider ||
        (typeof providerResult.thread_id === "string" &&
          typeof providerResult.run_id === "string")
      ) {
        const maybeThreadId = providerResult.thread_id;
        if (typeof maybeThreadId === "string" && maybeThreadId.trim()) {
          setThreadId(maybeThreadId);
        }
      }

      let finalResponse = initialResponse;
      const executionId = initialResponse.execution_id;
      const hasExecutionId =
        typeof executionId === "string" && executionId.trim();

      if (
        hasExecutionId &&
        !isCompletedStatus(initialResponse.status) &&
        !isFailedStatus(initialResponse.status)
      ) {
        const pollToken = activePollTokenRef.current + 1;
        activePollTokenRef.current = pollToken;
        for (let attempt = 0; attempt < 30; attempt += 1) {
          if (activePollTokenRef.current !== pollToken) {
            return;
          }
          await sleep(1500);
          const polledResponse = await getExecutionStatusMutation.mutateAsync({
            executionId: executionId.trim(),
          });
          finalResponse = polledResponse;
          if (
            isCompletedStatus(polledResponse.status) ||
            isFailedStatus(polledResponse.status)
          ) {
            break;
          }
        }
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: buildAssistantReplyFromExecution(finalResponse),
        toolTraces: extractToolTraces(finalResponse),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsResponding(false);
    } catch (error) {
      const technicalMessage =
        error instanceof Error
          ? error.message
          : "Failed to run deployment execution. Please try again.";
      const assistantMessage: ChatMessage = {
        id: `assistant-error-${Date.now()}`,
        role: "assistant",
        content: [
          `I couldn't complete this execution${modeLabelForMeta ? ` in ${modeLabelForMeta}` : ""}.`,
          "Try again, or verify the deployment tool inputs and required parameters.",
          "",
          "Technical details:",
          "```text",
          technicalMessage,
          "```",
        ].join("\n"),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsResponding(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[780px] max-w-[95vw] gap-0 overflow-hidden p-0">
        <DialogTitle className="border-b px-6 py-4">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-lg font-semibold text-foreground">
                Test your agent
              </div>
              <div className="mt-1 flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
                {isWatsonxProvider && (
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-sm bg-transparent p-0.5">
                    <WatsonxOrchestrateIcon className="h-5 w-5 object-contain" />
                  </span>
                )}
                <span className="truncate">{providerLabel}</span>
                <span aria-hidden="true">•</span>
                <span className="truncate font-medium text-foreground/90">
                  {deploymentName}
                </span>
                {showWatsonxModeBadge && modeBadgeLabel && (
                  <>
                    <span aria-hidden="true">•</span>
                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${modeBadgeClass}`}
                    >
                      {modeBadgeLabel}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        </DialogTitle>

        <div className="flex max-h-[62vh] min-h-[440px] flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
            {messages.length === 0 && !isResponding && (
              <div className="flex h-full min-h-[300px] items-center justify-center">
                <div className="flex max-w-md flex-col items-center text-center">
                  <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-muted/40">
                    <ForwardedIconComponent
                      name="Bot"
                      className="h-5 w-5 text-muted-foreground"
                    />
                  </div>
                  <p className="text-sm font-medium text-foreground">
                    Agent Chat
                  </p>
                </div>
              </div>
            )}
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "flex justify-end"
                    : "flex w-full justify-start"
                }
              >
                <div
                  className={
                    message.role === "user"
                      ? "max-w-[75%] rounded-2xl rounded-br-sm bg-foreground px-4 py-2 text-sm text-background"
                      : "w-full max-w-full rounded-2xl border border-border/40 bg-muted/10 px-4 py-3 text-sm leading-relaxed text-foreground"
                  }
                >
                  {message.role === "user" ? (
                    <span className="whitespace-pre-wrap">
                      {message.content}
                    </span>
                  ) : (
                    <>
                      <Markdown
                        remarkPlugins={[remarkGfm]}
                        className="markdown prose prose-sm max-w-full dark:prose-invert"
                        components={{
                          p({ children }) {
                            return <p className="my-2 leading-7">{children}</p>;
                          },
                          ul({ children }) {
                            return (
                              <ul className="my-2 list-disc space-y-1 pl-5">
                                {children}
                              </ul>
                            );
                          },
                          ol({ children }) {
                            return (
                              <ol className="my-2 list-decimal space-y-1 pl-5">
                                {children}
                              </ol>
                            );
                          },
                          li({ children }) {
                            return <li className="leading-7">{children}</li>;
                          },
                          pre({ children }) {
                            return <>{children}</>;
                          },
                          code({ className, children, ...props }) {
                            const content = String(children);
                            if (isCodeBlock(className, props, content)) {
                              return (
                                <SimplifiedCodeTabComponent
                                  language={extractLanguage(className)}
                                  code={content.replace(/\n$/, "")}
                                />
                              );
                            }
                            return (
                              <code className="rounded bg-muted px-1.5 py-0.5 text-[0.9em] text-foreground/95">
                                {children}
                              </code>
                            );
                          },
                          table({ children }) {
                            return (
                              <div className="my-2 overflow-x-auto">
                                <table className="w-full border-collapse">
                                  {children}
                                </table>
                              </div>
                            );
                          },
                          th({ children }) {
                            return (
                              <th className="border border-border bg-muted/30 px-2 py-1 text-left">
                                {children}
                              </th>
                            );
                          },
                          td({ children }) {
                            return (
                              <td className="border border-border px-2 py-1 align-top">
                                {children}
                              </td>
                            );
                          },
                        }}
                      >
                        {message.content}
                      </Markdown>
                      {message.toolTraces && message.toolTraces.length > 0 && (
                        <Disclosure
                          open={Boolean(expandedToolDetails[message.id])}
                          onOpenChange={(nextOpen) =>
                            setExpandedToolDetails((prev) => ({
                              ...prev,
                              [message.id]: nextOpen,
                            }))
                          }
                          className="mt-3 w-full overflow-hidden rounded-lg border border-border/40 bg-background/20"
                        >
                          {(() => {
                            const toolGroups = groupToolTraces(
                              message.toolTraces || [],
                            );
                            const hasToolErrors = toolGroups.some((group) =>
                              toolOutputIndicatesError(group.output),
                            );
                            return (
                              <>
                                <DisclosureTrigger className="w-full">
                                  <div className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:bg-muted/40">
                                    <span className="font-medium text-foreground/90">
                                      {`Tool details (${toolGroups.length})`}
                                      {hasToolErrors ? " • Error" : ""}
                                    </span>
                                    <ForwardedIconComponent
                                      name="ChevronDown"
                                      className={`h-4 w-4 transition-transform ${
                                        expandedToolDetails[message.id]
                                          ? "rotate-180"
                                          : ""
                                      }`}
                                    />
                                  </div>
                                </DisclosureTrigger>
                                <DisclosureContent>
                                  <div className="px-3 pb-3 pt-1">
                                    <div className="space-y-2">
                                      {toolGroups.map((group) => {
                                        const inputSnippet =
                                          toHighlightedSnippet(group.input);
                                        const outputSnippet =
                                          toHighlightedSnippet(group.output);
                                        const hasOutputError =
                                          toolOutputIndicatesError(
                                            group.output,
                                          );
                                        const outputErrorSummary =
                                          extractToolErrorSummary(group.output);

                                        return (
                                          <div
                                            key={`${message.id}-tool-group-${group.key}`}
                                            className="w-full rounded-md bg-muted/10 px-2 py-2 text-xs"
                                          >
                                            <div className="flex items-center justify-between gap-2">
                                              <div className="font-medium text-foreground">
                                                Tool: {group.toolName}
                                                {hasOutputError && (
                                                  <span className="ml-2 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                                                    Error
                                                  </span>
                                                )}
                                              </div>
                                              <div className="flex items-center gap-2">
                                                {group.input !== undefined && (
                                                  <button
                                                    type="button"
                                                    className="text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                                                    onClick={() =>
                                                      copyToolDetail(
                                                        group.input,
                                                        `${message.id}:${group.key}:input`,
                                                      )
                                                    }
                                                  >
                                                    {copiedToolDetailKey ===
                                                    `${message.id}:${group.key}:input`
                                                      ? "Copied input"
                                                      : "Copy input"}
                                                  </button>
                                                )}
                                                {group.output !== undefined && (
                                                  <button
                                                    type="button"
                                                    className="text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                                                    onClick={() =>
                                                      copyToolDetail(
                                                        group.output,
                                                        `${message.id}:${group.key}:output`,
                                                      )
                                                    }
                                                  >
                                                    {copiedToolDetailKey ===
                                                    `${message.id}:${group.key}:output`
                                                      ? "Copied output"
                                                      : "Copy output"}
                                                  </button>
                                                )}
                                              </div>
                                            </div>
                                            {inputSnippet && (
                                              <div className="mt-2">
                                                <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                                                  Input
                                                </div>
                                                <SimplifiedCodeTabComponent
                                                  language={
                                                    inputSnippet.language
                                                  }
                                                  code={inputSnippet.code}
                                                />
                                              </div>
                                            )}
                                            {outputSnippet && (
                                              <div className="mt-2">
                                                <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                                                  Output
                                                </div>
                                                {outputErrorSummary && (
                                                  <div className="mt-1 whitespace-pre-wrap break-words rounded-md border border-red-500/25 bg-red-500/5 px-2 py-1 text-[11px] text-red-700 dark:text-red-300">
                                                    {outputErrorSummary}
                                                  </div>
                                                )}
                                                <SimplifiedCodeTabComponent
                                                  language={
                                                    outputSnippet.language
                                                  }
                                                  code={outputSnippet.code}
                                                />
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                </DisclosureContent>
                              </>
                            );
                          })()}
                        </Disclosure>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            {isResponding && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ForwardedIconComponent
                  name="Loader2"
                  className="h-4 w-4 animate-spin"
                />
                Generating response...
              </div>
            )}
          </div>

          <div className="border-t px-5 py-4">
            <form
              className="flex items-center gap-2 rounded-2xl border border-input bg-background px-3 py-2"
              onSubmit={(event) => {
                event.preventDefault();
                handleSend();
              }}
            >
              <textarea
                ref={composerRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Say something..."
                className="max-h-36 min-h-10 flex-1 resize-none bg-transparent px-1 py-2.5 text-sm leading-5 text-foreground outline-none placeholder:text-muted-foreground"
                rows={1}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
              />
              <Button
                size="icon"
                className="h-9 w-9 rounded-full"
                disabled={!draft.trim() || isResponding}
                type="submit"
              >
                <ForwardedIconComponent
                  name={isResponding ? "Loader2" : "Send"}
                  className={`h-4 w-4 ${isResponding ? "animate-spin" : ""}`}
                />
              </Button>
            </form>
            <div className="mt-2 px-1 text-[11px] text-muted-foreground">
              Press Enter to send, Shift+Enter for a new line.
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
