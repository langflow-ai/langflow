// Lothal workspace (Story B.3) — the build bench. Rebuilt onto the B.1 design
// system: a themed surface with a phase-aware top bar and a split layout
// (clarification chat on the left, canvas on the right). The chat is wired to
// the real `/messages` + `/chat` endpoints — no scripted playback. While those
// are 501 stubs (Epic 1) the chat column shows the uniform NotReady state; it
// "goes live" with no UI change once the clarification backend lands. The right
// pane is the live D2 diagram canvas (Epic D.6) — double-click an element to
// reference it inline in the composer (Epic D.7), and approve it to advance to
// code generation (Epic D.11) — or the generated-code surface (Story B.5) once
// the build reaches a code phase.

import {
  type ReactNode,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  type Message,
  type Project,
  useCode,
  useMessages,
  useProject,
  useSendMessage,
} from "@/controllers/API/queries/lothal";
import useAuthStore from "@/stores/authStore";
import {
  AssistantQuestion,
  Button,
  ChatBubble,
  ChatComposer,
  type ChatComposerHandle,
  CodeView,
  EmptyHint,
  isCodePhase,
  isNotImplemented,
  LOTHAL_VERSION,
  LothalMark,
  NotReady,
  PhaseStepper,
  phaseLabel,
  StatusDot,
  SystemBlock,
  TopBar,
} from "../components";
import { ArtifactsPane } from "../components/ArtifactsPane";
import { PlanPane } from "../components/PlanPane";
import { PrototypePane } from "../components/PrototypePane";
import { LothalSurface } from "../theme/LothalSurface";

// The line shown when the conversation crosses a phase boundary.
function transitionNote(toPhase: string): string {
  switch (toPhase) {
    // Epic E.2 merged the two diagram phases into ARCHITECTURE.
    case "ARCHITECTURE":
      return "Requirements clear — designing the architecture";
    // Epic UI (U.10): the prototype stage sits between architecture approval and
    // code generation.
    case "PROTOTYPE":
      return "Architecture approved — building the prototype";
    // Epic U-PLAN: the planning stage sits between prototype approval and code gen.
    case "PLAN":
      return "Prototype approved — planning the build";
    case "CODE_GENERATION":
      return "Plan approved — generating the code";
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

function ChatPanel({
  project,
  composerRef,
  activeArtifact,
}: {
  project: Project;
  // Held by the Workspace so a double-clicked canvas element can drop a chip in
  // the composer (Epic D.7).
  composerRef: RefObject<ChatComposerHandle | null>;
  // The artifact the right pane is showing (Epic E.5) — a refine turn in the
  // ARCHITECTURE stage targets it so the edit lands on the right diagram/ADR.
  activeArtifact: string | null;
}) {
  const { data: messages, isLoading, isError, error } = useMessages(project.id);
  const send = useSendMessage(project.id);
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
      // Route a refine turn to the artifact the user is looking at; only in the
      // ARCHITECTURE stage (other phases ignore it, and the first/generation turn
      // has no map yet — the engine defaults a missing target).
      const artifact = project.phase === "ARCHITECTURE" ? activeArtifact : null;
      await send.mutateAsync({ content: trimmed, artifact });
      // Clear on success so the bubble doesn't stick if the /messages refetch
      // errors. The useEffect below is the backstop when the refetch succeeds.
      setPending(null);
    } catch {
      // Roll back the optimistic bubble and surface the failure inline.
      setPending(null);
      setSendFailed(true);
    }
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
    // genuine failure reaching the server.
    return isNotImplemented(error) ? (
      <NotReady title="The conversation isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the conversation"
        detail="Something went wrong loading this. Try again in a moment."
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

      <ChatComposer
        ref={composerRef}
        onSend={submit}
        disabled={send.isPending}
      />
    </div>
  );
}

// --- Code --------------------------------------------------------------------

function CodePanel({ project }: { project: Project }) {
  const { data: files, isLoading, isError, error } = useCode(project.id);

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
        Opening the generated code…
      </div>
    );
  }

  if (isError) {
    // Contract-first: a structured 501 means code generation isn't built yet
    // (Epic 4), so the pane shows the uniform NotReady state. Any other error
    // is a genuine failure reaching the server.
    return isNotImplemented(error) ? (
      <NotReady title="The code isn't ready yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the code"
        detail="Something went wrong loading this. Try again in a moment."
      />
    );
  }

  // `files` is `[]` while generation is still running.
  if (!files || files.length === 0) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <EmptyHint
          title="Generating the code…"
          sub="Lothal is writing the scaffold from your approved diagram. Files appear here as they're produced."
        />
      </div>
    );
  }

  return <CodeView files={files} />;
}

// --- Page --------------------------------------------------------------------

function WorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  // One project, fetched directly — the workspace doesn't need (or wait for)
  // the whole project list. A 404 leaves `project` unset → the not-found state.
  // Non-404 failures (5xx, network) surface as `isError` → distinct error state.
  const {
    data: project,
    isLoading,
    isError: projectIsError,
    error: projectError,
    refetch: refetchProject,
  } = useProject(projectId ?? "");
  const username = useAuthStore((s) => s.userData?.username);
  const initial = username ? username.charAt(0).toUpperCase() : "";
  // Bridges the right-pane canvas to the left-pane composer: a double-clicked
  // diagram element resolves to an anchor and drops an inline chip at the caret
  // (Epic D.7).
  const composerRef = useRef<ChatComposerHandle>(null);
  // The artifact the right pane is showing (Epic E.5). Lifted here so a refine
  // turn in the chat (left pane) targets the diagram/ADR the user is viewing.
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);

  // Tab title carries the open project ("Tide Tracker — Lothal"); restored on
  // the way out.
  useEffect(() => {
    if (project?.name) document.title = `${project.name} — Lothal`;
    return () => {
      document.title = "Lothal";
    };
  }, [project?.name]);

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
          Opening your project…
        </span>
      </div>
    );
  }

  // Non-404 error: a transient 5xx or network failure. Distinct from not-found
  // so the user isn’t misled into thinking their project was deleted.
  if (projectIsError) {
    const is404 =
      (projectError as { response?: { status?: number } } | null)?.response
        ?.status === 404;
    if (!is404) {
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
          <NotReady
            title="Couldn’t load this project"
            detail="Something went wrong reaching the server. Try again in a moment."
            action={
              <Button variant="accent" onClick={() => void refetchProject()}>
                Retry
              </Button>
            }
          />
        </div>
      );
    }
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
          sub="This project doesn’t exist — it may have been deleted."
        />
        <Button variant="accent" onClick={() => navigate("/lothal")}>
          Back to projects
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
              aria-label="Back to projects"
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
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-soft)" }}
            >
              v{LOTHAL_VERSION}
            </span>
          </span>
        }
        center={<PhaseStepper phase={project.phase} variant="stepper" />}
        right={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 16 }}
          >
            <StatusDot phase={project.phase} />
            <button
              type="button"
              aria-label={
                username ? `Account: ${username} — open settings` : "Settings"
              }
              onClick={() => navigate("/lothal/settings")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: "50%",
                border: "none",
                background: "var(--accent)",
                color: "var(--accent-fg)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {initial}
            </button>
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
          <ChatPanel
            project={project}
            composerRef={composerRef}
            activeArtifact={activeArtifact}
          />
        </div>

        {/* Right pane — switches by phase:
            • CODE_GENERATION/DONE → the generated-code surface (Story B.5);
            • PROTOTYPE → the embedded Open Design prototype pane (Epic UI U.8/U.9);
            • otherwise (CLARIFICATION/ARCHITECTURE) → the architecture
              doc-and-diagrams view (Epic E.5): the ADR as Markdown plus the
              diagram set as tabs. Double-clicking a box or arrow on a diagram
              drops an inline reference chip in the composer (Epic D.7); the
              active tab is the artifact a refine turn targets. It falls back to a
              phase-aware placeholder before generation and to NotReady while
              /artifacts can't load or render. */}
        <div style={{ flex: 1, minWidth: 0, background: "var(--paper-deep)" }}>
          {isCodePhase(project.phase) ? (
            <CodePanel project={project} />
          ) : project.phase === "PROTOTYPE" ? (
            <PrototypePane project={project} />
          ) : project.phase === "PLAN" ? (
            <PlanPane project={project} />
          ) : (
            <ArtifactsPane
              project={project}
              onAnchor={(a) => composerRef.current?.insertAnchor(a)}
              onActiveArtifactChange={setActiveArtifact}
            />
          )}
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
