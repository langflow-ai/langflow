import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useGetFlowAssistantModels } from "@/controllers/API/queries/assistant";
import {
  type FlowAssistantChatMessage,
  type MessageSegment,
  type ReasoningBlock,
  type ToolCallDetail,
  useFlowAssistantStore,
} from "@/stores/flowAssistantStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import ModelSelector from "./model-selector";

function ReasoningBlockDisplay({ reasoning }: { reasoning: ReasoningBlock }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 rounded-md border border-blue-200 bg-blue-50 text-xs dark:border-blue-800 dark:bg-blue-950/30">
      <button
        type="button"
        className="flex w-full items-center gap-1 px-2 py-1 text-left text-blue-700 hover:bg-blue-100 dark:text-blue-300 dark:hover:bg-blue-950/50"
        onClick={() => setExpanded((v) => !v)}
      >
        <ForwardedIconComponent
          name={expanded ? "ChevronDown" : "ChevronRight"}
          className="h-3 w-3"
        />
        <ForwardedIconComponent name="Brain" className="h-3 w-3" />
        <span className="font-medium">{reasoning.summary || "Reasoning"}</span>
      </button>
      {expanded && (
        <div className="p-2 text-blue-900 dark:text-blue-100">
          <div className="whitespace-pre-wrap rounded bg-blue-100 p-2 text-[11px] dark:bg-blue-900/30">
            {reasoning.content}
          </div>
        </div>
      )}
    </div>
  );
}

function SingleToolCallDisplay({ toolCall }: { toolCall: ToolCallDetail }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 rounded-md border border-border bg-muted/50 text-xs">
      <button
        type="button"
        className="flex w-full items-center gap-1 px-2 py-1 text-left text-muted-foreground hover:bg-muted"
        onClick={() => setExpanded((v) => !v)}
      >
        <ForwardedIconComponent
          name={expanded ? "ChevronDown" : "ChevronRight"}
          className="h-3 w-3"
        />
        {toolCall.status === "running" ? (
          <ForwardedIconComponent
            name="Loader2"
            className="h-3 w-3 animate-spin"
          />
        ) : toolCall.status === "error" ? (
          <ForwardedIconComponent
            name="AlertCircle"
            className="h-3 w-3 text-red-500"
          />
        ) : toolCall.status === "done" ? (
          <ForwardedIconComponent
            name="Check"
            className="h-3 w-3 text-green-500"
          />
        ) : (
          <ForwardedIconComponent name="Wrench" className="h-3 w-3" />
        )}
        <span className="font-medium text-primary">{toolCall.name}</span>
      </button>
      {expanded && (
        <div className="space-y-1 p-2">
          <div className="text-muted-foreground">
            <span className="font-medium">Input:</span>
            <pre className="mt-0.5 overflow-auto whitespace-pre-wrap rounded bg-muted p-1 text-[10px]">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {toolCall.result && (
            <div className="text-muted-foreground">
              <span className="font-medium text-green-600">Result:</span>
              <pre className="mt-0.5 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted p-1 text-[10px]">
                {toolCall.result}
              </pre>
            </div>
          )}
          {toolCall.error && (
            <div className="text-red-500">
              <span className="font-medium">Error:</span> {toolCall.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TextSegmentDisplay({
  content,
  isStreaming,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  if (!content && !isStreaming) return null;

  return (
    <div className="markdown prose max-w-full text-sm font-normal dark:prose-invert">
      <Markdown
        remarkPlugins={[remarkGfm]}
        linkTarget="_blank"
        rehypePlugins={[rehypeMathjax]}
        className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
        components={{
          p({ node, ...props }) {
            return (
              <span className="block w-fit max-w-full">{props.children}</span>
            );
          },
          pre({ node, ...props }) {
            return <>{props.children}</>;
          },
          code: ({ node, inline, className, children, ...props }) => {
            let textContent = children as string;
            if (
              Array.isArray(children) &&
              children.length === 1 &&
              typeof children[0] === "string"
            ) {
              textContent = children[0] as string;
            }
            if (typeof textContent === "string") {
              if (textContent.length) {
                if (textContent[0] === "▍") {
                  return <span className="form-modal-markdown-span"></span>;
                }
              }

              const match = /language-(\w+)/.exec(className || "");

              return !inline ? (
                <SimplifiedCodeTabComponent
                  language={(match && match[1]) || ""}
                  code={String(textContent).replace(/\n$/, "")}
                />
              ) : (
                <code className={className} {...props}>
                  {textContent}
                </code>
              );
            }
            return null;
          },
        }}
      >
        {content || (isStreaming ? "…" : "")}
      </Markdown>
    </div>
  );
}

function MessageItem({
  message,
  onEdit,
}: {
  message: FlowAssistantChatMessage;
  onEdit: (id: string, newContent: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(message.content);

  const handleSave = () => {
    onEdit(message.id, editText);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditText(message.content);
    setEditing(false);
  };

  const renderSegments = () => {
    const segments = message.segments;
    if (!segments || segments.length === 0) {
      return (
        <TextSegmentDisplay
          content={message.content}
          isStreaming={message.isStreaming}
        />
      );
    }

    return segments.map((segment, idx) => {
      const isLastSegment = idx === segments.length - 1;
      if (segment.type === "text") {
        return (
          <TextSegmentDisplay
            key={idx}
            content={segment.content}
            isStreaming={isLastSegment && message.isStreaming}
          />
        );
      }
      if (segment.type === "reasoning") {
        return (
          <ReasoningBlockDisplay key={idx} reasoning={segment.reasoning} />
        );
      }
      return <SingleToolCallDisplay key={idx} toolCall={segment.toolCall} />;
    });
  };

  return (
    <div
      className={cn(
        "group relative rounded-md border border-border p-2 text-sm",
        message.role === "user" ? "bg-muted" : "bg-background",
      )}
    >
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          {message.role === "user" ? "You" : "Assistant"}
          {message.isStreaming && (
            <ForwardedIconComponent
              name="Loader2"
              className="h-3 w-3 animate-spin"
            />
          )}
        </span>
        {message.role === "user" && !editing && (
          <button
            type="button"
            className="opacity-0 transition-opacity group-hover:opacity-100"
            onClick={() => setEditing(true)}
          >
            <ForwardedIconComponent name="Pen" className="h-3 w-3" />
          </button>
        )}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <Textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="min-h-[60px] resize-none text-sm"
            autoFocus
          />
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="sm" onClick={handleCancel}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>
      ) : message.role === "assistant" ? (
        <div>{renderSegments()}</div>
      ) : (
        <div className="whitespace-pre-wrap">
          {message.content || (message.isStreaming ? "…" : "")}
        </div>
      )}
    </div>
  );
}

export default function FlowAssistantPanel(): JSX.Element | null {
  const isOpen = useFlowAssistantStore((s) => s.isOpen);
  const close = useFlowAssistantStore((s) => s.close);
  const messages = useFlowAssistantStore((s) => s.messages);
  const addMessage = useFlowAssistantStore((s) => s.addMessage);
  const updateMessage = useFlowAssistantStore((s) => s.updateMessage);
  const appendToMessage = useFlowAssistantStore((s) => s.appendToMessage);
  const addToolCallToMessage = useFlowAssistantStore(
    (s) => s.addToolCallToMessage,
  );
  const updateLastToolCall = useFlowAssistantStore((s) => s.updateLastToolCall);
  const addReasoningToMessage = useFlowAssistantStore(
    (s) => s.addReasoningToMessage,
  );
  const clear = useFlowAssistantStore((s) => s.clear);
  const isStreaming = useFlowAssistantStore((s) => s.isStreaming);
  const setStreaming = useFlowAssistantStore((s) => s.setStreaming);
  const selectedModel = useFlowAssistantStore((s) => s.selectedModel);
  const setSelectedModel = useFlowAssistantStore((s) => s.setSelectedModel);
  const flowId = useFlowsManagerStore((s) => s.currentFlowId);

  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastToolNameRef = useRef<string>("");

  const refetchFlow = useCallback(async () => {
    if (!flowId) return;
    try {
      const response = await api.get<FlowType>(`${getURL("FLOWS")}/${flowId}`);
      const { flows } = processFlows([response.data]);
      if (flows[0]) {
        useFlowStore.getState().resetFlow(flows[0]);
      }
    } catch (err) {
      console.error("Failed to refetch flow after assistant changes:", err);
    }
  }, [flowId]);

  const { data: modelsData, isLoading: modelsLoading } =
    useGetFlowAssistantModels({ enabled: isOpen });

  useEffect(() => {
    if (isOpen && !selectedModel && modelsData?.models?.length) {
      setSelectedModel(modelsData.models[0].slug);
    }
  }, [isOpen, selectedModel, modelsData, setSelectedModel]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const history = useMemo(
    () =>
      messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({
          role: m.role,
          content: m.content,
        })),
    [messages],
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || !flowId || isStreaming) return;
    setInput("");
    setError(null);

    addMessage({ role: "user", content: text, createdAt: Date.now() });
    const assistantMsgId = addMessage({
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      isStreaming: true,
      toolCalls: [],
    });

    setStreaming(true);
    abortRef.current = new AbortController();

    try {
      const response = await fetch(getURL("FLOW_ASSISTANT_STREAM"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        signal: abortRef.current.signal,
        body: JSON.stringify({
          flow_id: flowId,
          message: text,
          history,
          model: selectedModel,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              switch (eventType) {
                case "text":
                  appendToMessage(assistantMsgId, data.content || "");
                  break;
                case "reasoning":
                  addReasoningToMessage(assistantMsgId, {
                    content: data.content || "",
                    summary: data.summary,
                  });
                  break;
                case "tool_start":
                  lastToolNameRef.current = data.name || "";
                  addToolCallToMessage(assistantMsgId, {
                    name: data.name,
                    arguments: {},
                    status: "pending",
                  });
                  break;
                case "tool_call":
                  lastToolNameRef.current =
                    data.name || lastToolNameRef.current;
                  updateLastToolCall(assistantMsgId, {
                    arguments: data.arguments,
                    status: "running",
                  });
                  break;
                case "tool_result":
                  updateLastToolCall(assistantMsgId, {
                    result: data.result,
                    error: data.error,
                    status: data.error ? "error" : "done",
                  });
                  if (
                    !data.error &&
                    lastToolNameRef.current === "lf_workflow_patch"
                  ) {
                    refetchFlow();
                  }
                  break;
                case "done":
                  updateMessage(assistantMsgId, {
                    content: data.message,
                    isStreaming: false,
                  });
                  break;
                case "error":
                  setError(data.message || "Unknown error");
                  updateMessage(assistantMsgId, { isStreaming: false });
                  break;
              }
            } catch {
              // ignore parse errors
            }
            eventType = "";
          }
        }
      }

      updateMessage(assistantMsgId, { isStreaming: false });
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setError(err.message || "Request failed");
        updateMessage(assistantMsgId, { isStreaming: false });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [
    input,
    flowId,
    isStreaming,
    selectedModel,
    history,
    addMessage,
    appendToMessage,
    addReasoningToMessage,
    addToolCallToMessage,
    updateLastToolCall,
    updateMessage,
    setStreaming,
    refetchFlow,
  ]);

  const handleEditMessage = (id: string, newContent: string) => {
    updateMessage(id, { content: newContent });
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  if (!isOpen) return null;

  return (
    <div className="absolute right-0 top-0 z-40 h-full w-[420px] max-w-[90vw] border-l border-border bg-background">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="font-medium">Assistant</span>
            <ModelSelector
              models={modelsData?.models ?? []}
              value={selectedModel}
              onChange={setSelectedModel}
              disabled={isStreaming}
              isLoading={modelsLoading}
            />
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={clear}
              className="h-7 px-2 text-xs"
              disabled={isStreaming}
            >
              Clear
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={close}
              className="h-7 px-2 text-xs"
            >
              Close
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-3">
          <div className="flex flex-col gap-3">
            {messages.map((m) => (
              <MessageItem key={m.id} message={m} onEdit={handleEditMessage} />
            ))}
            <div ref={messagesEndRef} />
            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
                {error}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-border p-3">
          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !isStreaming) {
                  e.preventDefault();
                  send();
                }
              }}
              className="min-h-[44px] w-full resize-none text-sm"
              placeholder="Describe what to do with the workflow…"
              disabled={isStreaming}
            />
            {isStreaming ? (
              <Button
                onClick={stopStreaming}
                variant="destructive"
                className="shrink-0"
              >
                <ForwardedIconComponent name="Square" className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={send}
                disabled={input.trim().length === 0 || !selectedModel}
                className="shrink-0"
              >
                <ForwardedIconComponent name="Send" className="h-4 w-4" />
              </Button>
            )}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            The assistant can read and modify your workflow via MCP tools.
          </div>
        </div>
      </div>
    </div>
  );
}
