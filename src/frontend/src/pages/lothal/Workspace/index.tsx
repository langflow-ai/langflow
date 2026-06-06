// Lothal workspace (Story B.3) — the build bench. Rebuilt onto the B.1 design
// system: a themed surface with a phase-aware top bar and a split layout
// (clarification chat on the left, canvas on the right). The chat is wired to
// the real `/messages` + `/chat` endpoints — no scripted playback. While those
// are 501 stubs (Epic 1) the chat column shows the uniform NotReady state; it
// "goes live" with no UI change once the clarification backend lands. The
// canvas is a placeholder until Story B.4 brings the real @xyflow/react canvas.

import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  type Message,
  type Project,
  useMessages,
  useProjects,
  useSendMessage,
} from "@/controllers/API/queries/lothal";
import useAuthStore from "@/stores/authStore";
import {
  AssistantQuestion,
  Button,
  CanvasSurface,
  ChatBubble,
  ChatDock,
  EmptyHint,
  isNotImplemented,
  LothalMark,
  NotReady,
  PhaseStepper,
  phaseLabel,
  StatusDot,
  SystemBlock,
  TopBar,
} from "../components";
import { LothalSurface } from "../theme/LothalSurface";

// The line shown when the conversation crosses a phase boundary.
function transitionNote(toPhase: string): string {
  switch (toPhase) {
    case "DIAGRAM_GENERATION":
      return "Requirements clear — sketching the diagram";
    case "DIAGRAM_REFINEMENT":
      return "Refining the diagram";
    case "CODE_GENERATION":
      return "Diagram approved — generating the code";
    case "DONE":
      return "Delivered";
    default:
      return `Now ${phaseLabel(toPhase)}`;
  }
}

function ArrowLeft({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M9.5 3.5 5 8l4.5 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Pulsing dots while the assistant reply is in flight.
function ThinkingBubble() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 5,
      }}
    >
      <span className="label" style={{ fontSize: 9.5, paddingInline: 2 }}>
        Lothal
      </span>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "11px 14px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          borderBottomLeftRadius: 4,
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="pulse"
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "var(--ink-soft)",
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

// --- Chat --------------------------------------------------------------------

function ChatPanel({ project }: { project: Project }) {
  const { data: messages, isLoading, isError, error } = useMessages(project.id);
  const send = useSendMessage(project.id);
  const [input, setInput] = useState("");
  // The user's in-flight turn, shown optimistically until the refetched thread
  // (which now includes it) replaces it.
  const [pending, setPending] = useState<string | null>(null);
  const [sendFailed, setSendFailed] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // A fresh message list means the send round-tripped — drop the optimistic
  // bubble (the real user + assistant messages are now in `messages`).
  useEffect(() => {
    setPending(null);
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || send.isPending) return;
    setSendFailed(false);
    setPending(trimmed);
    try {
      await send.mutateAsync(trimmed);
    } catch {
      // Roll back the optimistic bubble and surface the failure inline.
      setPending(null);
      setSendFailed(true);
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setInput("");
    submit(trimmed);
  };

  if (isLoading) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          color: "var(--ink-soft)",
        }}
      >
        Opening the conversation…
      </div>
    );
  }

  if (isError) {
    // Contract-first: a structured 501 means the backend isn't built yet, so
    // the whole column shows the uniform NotReady state. Any other error is a
    // genuine failure reaching the dockyard.
    return isNotImplemented(error) ? (
      <NotReady title="The conversation isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the conversation"
        detail="Something went wrong reaching the dockyard. Try again in a moment."
      />
    );
  }

  const list: Message[] = messages ?? [];
  const lastMsg = list[list.length - 1];
  // Chips belong to the active question only: the latest message, when it's an
  // assistant reply still offering suggestions (clarification). Once the phase
  // advances the backend returns `suggestions: []`, so they disappear on their
  // own — and they're hidden while a reply is in flight.
  const showChips =
    !pending &&
    !send.isPending &&
    lastMsg?.role === "ASSISTANT" &&
    (lastMsg.suggestions?.length ?? 0) > 0;

  const thread: ReactNode[] = [];
  let prevPhase: string | null = null;
  list.forEach((m, i) => {
    if (prevPhase !== null && m.phase !== prevPhase) {
      thread.push(
        <SystemBlock key={`sys-${m.id}`}>
          {transitionNote(m.phase)}
        </SystemBlock>,
      );
    }
    prevPhase = m.phase;
    const isLast = i === list.length - 1;
    thread.push(
      <ChatBubble key={m.id} role={m.role} content={m.content}>
        {isLast && showChips ? (
          <AssistantQuestion
            suggestions={m.suggestions}
            onPick={submit}
            disabled={send.isPending}
          />
        ) : null}
      </ChatBubble>,
    );
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: "18px var(--pad)",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {list.length === 0 && !pending ? (
          <EmptyHint
            title="Start the conversation"
            sub="Describe what you want to build. Lothal asks focused questions until the spec is clear, then sketches the diagram."
          />
        ) : (
          thread
        )}
        {pending && <ChatBubble role="USER" content={pending} />}
        {send.isPending && <ThinkingBubble />}
        {sendFailed && (
          <div
            style={{
              alignSelf: "center",
              fontSize: 12,
              color: "var(--warn)",
            }}
          >
            Couldn’t send that — please try again.
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <ChatDock
        value={input}
        onChange={setInput}
        onSend={handleSend}
        disabled={send.isPending}
      />
    </div>
  );
}

// --- Page --------------------------------------------------------------------

function WorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: projects, isLoading } = useProjects();
  const username = useAuthStore((s) => s.userData?.username);
  const initial = username ? username.charAt(0).toUpperCase() : "";
  const project = projects?.find((p) => p.id === projectId);

  if (isLoading) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          className="serif"
          style={{
            fontSize: 22,
            color: "var(--ink-mute)",
            fontStyle: "italic",
          }}
        >
          Opening the workshop…
        </span>
      </div>
    );
  }

  if (!project) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
        }}
      >
        <EmptyHint
          title="Project not found"
          sub="This build isn’t in your harbor — it may have been deleted."
        />
        <Button variant="accent" onClick={() => navigate("/lothal")}>
          Back to the harbor
        </Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <TopBar
        dense
        left={
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              minWidth: 0,
            }}
          >
            <button
              type="button"
              aria-label="Back to the harbor"
              onClick={() => navigate("/lothal")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: 7,
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--ink-mute)",
                cursor: "pointer",
              }}
            >
              <ArrowLeft />
            </button>
            <span style={{ color: "var(--accent)", display: "inline-flex" }}>
              <LothalMark size={18} />
            </span>
            <span
              className="serif"
              style={{
                fontSize: 19,
                color: "var(--ink)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: 260,
              }}
            >
              {project.name}
            </span>
          </span>
        }
        center={<PhaseStepper phase={project.phase} variant="stepper" />}
        right={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 16 }}
          >
            <StatusDot phase={project.phase} />
            <span
              aria-label={username ? `Account: ${username}` : "Account"}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: "var(--accent)",
                color: "var(--accent-fg)",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {initial}
            </span>
          </span>
        }
      />

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Chat — left */}
        <div
          style={{
            flexBasis: "40%",
            minWidth: 360,
            maxWidth: 540,
            borderRight: "1px solid var(--border)",
            background: "var(--paper)",
            minHeight: 0,
          }}
        >
          <ChatPanel project={project} />
        </div>

        {/* Canvas — right. The real @xyflow/react sequence-diagram canvas
            (Story B.4); falls back to a phase-aware placeholder before a
            diagram exists and to NotReady while /diagram is a 501 stub. */}
        <div style={{ flex: 1, minWidth: 0, background: "var(--paper-deep)" }}>
          <CanvasSurface project={project} />
        </div>
      </div>
    </div>
  );
}

export default function Workspace() {
  return (
    <LothalSurface>
      <WorkspaceView />
    </LothalSurface>
  );
}
