import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePostA2AMessage } from "@/controllers/API/queries/a2a/use-post-a2a-message";
import {
  type A2AResult,
  type A2ATaskState,
  parseA2AReply,
} from "@/controllers/API/queries/a2a/utils";
import { cn } from "@/utils/utils";

type TranscriptMessage = {
  role: "user" | "agent";
  text: string;
  state?: A2ATaskState;
  failed?: boolean;
};

const errorDetail = (e: unknown, fallback: string): string => {
  const err = e as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return err.response?.data?.detail || err.message || fallback;
};

const STATE_STYLE: Record<string, string> = {
  working: "bg-muted text-muted-foreground",
  submitted: "bg-muted text-muted-foreground",
  completed: "bg-accent-emerald text-accent-emerald-foreground",
  "input-required": "bg-accent-amber/20 text-accent-amber-foreground",
  failed: "bg-error-background text-error-foreground",
  canceled: "bg-muted text-muted-foreground",
};

function StateChip({ state }: { state: A2ATaskState | "working" }) {
  const { t } = useTranslation();
  const label =
    state === "completed"
      ? t("agentTab.stateCompleted")
      : state === "input-required"
        ? t("agentTab.stateInputRequired")
        : state === "failed"
          ? t("agentTab.stateFailed")
          : t("agentTab.stateWorking");
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[11px] font-medium",
        STATE_STYLE[state] ?? "bg-muted text-muted-foreground",
      )}
    >
      {`◆ ${label}`}
    </span>
  );
}

function Bubble({ message }: { message: TranscriptMessage }) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  return (
    <div
      className={cn(
        "flex flex-col gap-1",
        isUser ? "items-end" : "items-start",
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span>
          {isUser ? t("agentTab.senderYou") : t("agentTab.senderAgent")}
        </span>
        {message.state && <StateChip state={message.state} />}
      </div>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-mmd",
          message.failed
            ? "bg-error-background text-error-foreground"
            : isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted",
        )}
      >
        {message.text}
      </div>
      {message.state === "input-required" && (
        <span className="text-xs text-accent-amber-foreground">
          {t("agentTab.inputRequiredHint")}
        </span>
      )}
    </div>
  );
}

export default function AgentTestConversation({
  flowId,
  isPublished,
  serverEnabled,
  requiresApiKey,
}: {
  flowId: string;
  isPublished: boolean;
  serverEnabled: boolean;
  requiresApiKey: boolean;
}) {
  const { t } = useTranslation();
  const { mutateAsync: sendMessage, isPending: isSending } =
    usePostA2AMessage();

  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [input, setInput] = useState("");
  const [apiKey, setApiKey] = useState("");
  // contextId threads memory across turns; taskId is kept only while a task is
  // paused (input-required) so the next send resumes it.
  const [contextId, setContextId] = useState<string | undefined>();
  const [taskId, setTaskId] = useState<string | undefined>();
  const lastState = messages.filter((m) => m.role === "agent").at(-1)?.state;

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, isSending]);

  const reset = () => {
    setMessages([]);
    setContextId(undefined);
    setTaskId(undefined);
  };

  const canSend =
    isPublished &&
    serverEnabled &&
    !!input.trim() &&
    !isSending &&
    (!requiresApiKey || !!apiKey.trim());

  const handleSend = async () => {
    if (!canSend) return;
    const text = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const data = await sendMessage({
        flowId,
        message: text,
        contextId,
        taskId,
        apiKey: requiresApiKey ? apiKey.trim() : undefined,
      });
      if (data?.error) {
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            text: data.error?.message ?? t("agentTab.testRequestFailed"),
            state: "failed",
            failed: true,
          },
        ]);
        setTaskId(undefined);
        return;
      }
      const result = (data?.result ?? {}) as A2AResult;
      const state = result.status?.state;
      // Echo whatever contextId the server assigns (it namespaces the raw value).
      if (result.contextId) setContextId(result.contextId);
      // Keep the task id only while it's parked for input; a terminal task is done.
      setTaskId(state === "input-required" ? result.id : undefined);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: parseA2AReply(result) || t("agentTab.testNoText"),
          state,
          failed: state === "failed",
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: errorDetail(e, t("agentTab.testRequestFailed")),
          state: "failed",
          failed: true,
        },
      ]);
      setTaskId(undefined);
    }
  };

  const turnCount = messages.filter((m) => m.role === "user").length;
  const chipState: A2ATaskState | "working" | undefined = isSending
    ? "working"
    : lastState;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium">{t("agentTab.testTitle")}</span>
          <span className="text-mmd text-muted-foreground">
            {t("agentTab.testSubtitle")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {chipState && <StateChip state={chipState} />}
          {contextId && (
            <span className="text-xs text-muted-foreground">
              {t("agentTab.turns", { count: turnCount })}
            </span>
          )}
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={reset}>
              {t("agentTab.testReset")}
            </Button>
          )}
        </div>
      </div>

      {/* Transcript */}
      <div
        ref={scrollRef}
        data-testid="agent-transcript"
        className="flex-1 overflow-y-auto px-6 py-4"
      >
        {!serverEnabled ? (
          <p className="text-mmd text-muted-foreground">
            {t("agentTab.testServerOff")}
          </p>
        ) : !isPublished ? (
          <p className="text-mmd text-muted-foreground">
            {t("agentTab.testPublishFirst")}
          </p>
        ) : messages.length === 0 ? (
          <p className="text-mmd text-muted-foreground">
            {t("agentTab.testEmpty")}
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((message, i) => (
              <Bubble key={i} message={message} />
            ))}
            {isSending && (
              <span className="text-xs text-muted-foreground">
                {`◆ ${t("agentTab.stateWorking")}…`}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Composer */}
      {serverEnabled && isPublished && (
        <div className="flex flex-col gap-2 border-t px-6 py-3">
          {requiresApiKey && (
            <div className="flex flex-col gap-1">
              <Input
                type="password"
                placeholder={t("agentTab.restrictedInputPlaceholder")}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                data-testid="agent-test-apikey"
              />
              <span className="text-xs text-muted-foreground">
                {t("agentTab.restrictedNote")}
              </span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Input
              placeholder={t("agentTab.testPlaceholder")}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && canSend) handleSend();
              }}
              data-testid="agent-test-input"
            />
            <Button
              onClick={handleSend}
              loading={isSending}
              disabled={!canSend}
              data-testid="agent-test-send"
            >
              <ForwardedIconComponent name="Send" className="h-4 w-4" />
              {t("agentTab.testSend")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
