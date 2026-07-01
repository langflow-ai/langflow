// The Workspace's right pane during the ARCHITECTURE stage (Epic E.5). Replaces
// the single-SVG diagram view with the full architecture output: an Architecture
// Decision Record rendered as Markdown plus the diagram set, each surfaced as a
// tab. The artifact map comes from GET /artifacts (Epic E.4) — the ADR Markdown
// verbatim and a server-rendered SVG per `diagrams/*.d2` (the frontend ships no
// D2 compiler of its own; it renders the ADR markdown and displays the SVGs).
//
// The active tab is lifted to the Workspace via `onActiveArtifactChange`, so a
// refine turn in the chat targets the artifact the user is looking at (Epic E.3
// routes the edit to that key). Double-clicking an element on a diagram tab drops
// an inline anchor chip in the composer, exactly as the old canvas did (D.7).
//
// Phase/loading/empty states:
//   before ARCHITECTURE     → phase-aware placeholder, no fetch (phase-gated)
//   loading                 → "opening" line
//   501 (stub)              → NotReady ("not live yet")
//   other error             → NotReady ("couldn't load")
//   empty map ({})          → placeholder ("designing…")
//   map present             → the tabbed ADR + diagrams view

import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Project } from "@/controllers/API/queries/lothal";
import {
  useApproveDiagram,
  useArtifacts,
  useGenerateArchitecture,
} from "@/controllers/API/queries/lothal";
import { ADR_PATH, orderArtifacts } from "./artifacts";
import { Button } from "./Button";
import { CanvasPlaceholder } from "./CanvasPlaceholder";
import { D2Canvas } from "./D2Canvas";
import type { Anchor } from "./d2/anchor";
import { isNotImplemented, NotReady } from "./NotReady";
import { phaseIndex } from "./phases";

function PaneLoading({ label }: { label: string }) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 13,
        color: "var(--ink-soft)",
      }}
    >
      {label}
    </div>
  );
}

// The ADR tab: LLM-authored Markdown. react-markdown (v9) doesn't render raw
// HTML unless rehype-raw is added, so the content can't inject scripting; we
// just style the rendered prose. Scrolls within the pane.
function AdrView({ content }: { content: string }) {
  return (
    <div className="lothal-adr-scroll">
      <article className="lothal-adr">
        <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
      </article>
    </div>
  );
}

// One diagram tab: the server-rendered SVG on the pannable/zoomable canvas, or —
// when the backend couldn't render it (compiler unavailable / render failure, a
// `null` svg) — a NotReady, since stored D2 is compile-validated at generation
// (E.3) so a missing SVG is an environment fault, not a bad diagram.
function DiagramView({
  svg,
  onAnchor,
}: {
  svg: string | null | undefined;
  onAnchor?: (anchor: Anchor) => void;
}) {
  if (!svg) {
    return (
      <NotReady
        title="Couldn't render this diagram"
        detail="The diagram is ready but couldn't be drawn just now. Try again in a moment."
      />
    );
  }
  return <D2Canvas svg={svg} onAnchor={onAnchor} />;
}

export function ArtifactsPane({
  project,
  onAnchor,
  onActiveArtifactChange,
}: {
  project: Project;
  /** A double-clicked diagram element drops a chip in the composer (Epic D.7). */
  onAnchor?: (anchor: Anchor) => void;
  /** Reports the active artifact key up so a refine turn targets it (Epic E.3). */
  onActiveArtifactChange?: (path: string | null) => void;
}) {
  // The artifact map only exists from ARCHITECTURE onward; before that the
  // endpoint is phase-gated, so we don't even fetch it.
  const hasArchitecture = phaseIndex(project.phase) >= 1;
  const { data, isLoading, isError, error } = useArtifacts(
    project.id,
    hasArchitecture,
  );

  // Auto-generate on entry (phase-gates): the ARCHITECTURE stage no longer waits
  // for the user to send a chat turn. Once the read confirms an empty map, fire
  // generation exactly once so the ADR + diagram set appear on their own — the fix
  // for the "stuck designing…" hang. The ref guards against the polling refetch
  // re-firing it across renders.
  const generate = useGenerateArchitecture(project.id);
  const seededRef = useRef(false);
  useEffect(() => {
    seededRef.current = false;
  }, [project.id]);
  const artifactCount = Object.keys(data?.artifacts ?? {}).length;
  useEffect(() => {
    if (
      project.phase === "ARCHITECTURE" &&
      hasArchitecture &&
      !isLoading &&
      !isError &&
      data !== undefined &&
      artifactCount === 0 &&
      !seededRef.current &&
      !generate.isPending
    ) {
      seededRef.current = true;
      generate.mutate();
    }
  }, [
    project.phase,
    hasArchitecture,
    isLoading,
    isError,
    data,
    artifactCount,
    generate,
  ]);

  const tabs = useMemo(
    () => orderArtifacts(Object.keys(data?.artifacts ?? {})),
    [data?.artifacts],
  );

  // The selected tab. Defaults to the ADR (it leads the set) once tabs load, and
  // self-heals if the active key vanishes from the map.
  const [activePath, setActivePath] = useState<string | null>(null);
  useEffect(() => {
    if (tabs.length === 0) {
      if (activePath !== null) setActivePath(null);
      return;
    }
    const stillValid = activePath && tabs.some((t) => t.path === activePath);
    if (!stillValid) {
      const adr = tabs.find((t) => t.path === ADR_PATH);
      setActivePath(adr?.path ?? tabs[0].path);
    }
  }, [tabs, activePath]);

  // Surface the active artifact to the Workspace so the composer's next turn
  // refines it. Null while there's nothing to refine (loading / empty / pre-
  // architecture) — the chat then sends no target and the engine defaults it.
  useEffect(() => {
    onActiveArtifactChange?.(activePath);
  }, [activePath, onActiveArtifactChange]);

  // --- Approve the architecture (Epic D.11; phase merged in E.2; retarget U.0) ---
  // Approving advances the project to the PROTOTYPE stage on the server (Epic UI
  // U.0 retargeted approve from CODE_GENERATION to PROTOTYPE); the project query
  // then invalidates, the phase flips, and the parent swaps this pane for the
  // prototype pane. Gated on the ARCHITECTURE phase and a non-empty artifact set
  // so it isn't offered before generation has produced anything (the backend
  // rejects an approve outside ARCHITECTURE, or with no diagram, with a 409).
  const approve = useApproveDiagram(project.id);
  const [failed, setFailed] = useState(false);
  // Latches on a successful approve so a quick second click can't hit the server
  // (now CODE_GENERATION) and 409 in the brief window before the refetch flips
  // the phase and unmounts this pane.
  const [approved, setApproved] = useState(false);
  const canApprove = project.phase === "ARCHITECTURE" && tabs.length > 0;

  // Clear the latched approve state when the workspace switches projects.
  useEffect(() => {
    setApproved(false);
    setFailed(false);
  }, [project.id]);

  const onApprove = async () => {
    if (approve.isPending || approved) return;
    setFailed(false);
    try {
      await approve.mutateAsync();
      setApproved(true);
    } catch {
      setFailed(true);
    }
  };

  // --- States --------------------------------------------------------------

  if (!hasArchitecture) {
    return <CanvasPlaceholder phase={project.phase} />;
  }
  if (isLoading) {
    return <PaneLoading label="Opening the architecture…" />;
  }
  if (isError) {
    return isNotImplemented(error) ? (
      <NotReady title="The architecture isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the architecture"
        detail="Something went wrong loading this. Try again in a moment."
      />
    );
  }
  // Endpoint is live but the map is still empty. In ARCHITECTURE that means the
  // auto-generation (above) is in flight → show a designing state, or a retry if
  // that call failed. Earlier phases keep the phase-aware placeholder.
  if (tabs.length === 0) {
    if (project.phase === "ARCHITECTURE") {
      if (generate.isError) {
        return (
          <NotReady
            title="Couldn't start the architecture"
            detail="The design engine couldn't be reached to begin generating. Try again in a moment."
            action={
              <Button
                variant="accent"
                onClick={() => generate.mutate()}
                disabled={generate.isPending}
              >
                {generate.isPending ? "Retrying…" : "Retry"}
              </Button>
            }
          />
        );
      }
      return (
        <PaneLoading label="Designing the architecture — an ADR and diagram set…" />
      );
    }
    return <CanvasPlaceholder phase={project.phase} />;
  }

  const active = tabs.find((t) => t.path === activePath) ?? tabs[0];
  const artifacts = data?.artifacts ?? {};
  const svgs = data?.svgs ?? {};

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
        className="lothal-artifact-tabs"
        role="tablist"
        aria-label="Artifacts"
      >
        {tabs.map((t) => (
          <button
            key={t.path}
            type="button"
            role="tab"
            aria-selected={t.path === active.path}
            className={
              t.path === active.path
                ? "lothal-artifact-tab is-active"
                : "lothal-artifact-tab"
            }
            onClick={() => setActivePath(t.path)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        {active.kind === "doc" ? (
          <AdrView content={artifacts[active.path] ?? ""} />
        ) : (
          <DiagramView svg={svgs[active.path]} onAnchor={onAnchor} />
        )}
      </div>

      {canApprove && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 12,
            padding: "10px var(--pad)",
            borderTop: "1px solid var(--border)",
            background: "var(--paper)",
          }}
        >
          {failed && (
            <span style={{ fontSize: 12, color: "var(--warn)" }}>
              Couldn’t approve just now — try again.
            </span>
          )}
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            Happy with the architecture?
          </span>
          <Button
            variant="accent"
            onClick={onApprove}
            disabled={approve.isPending || approved}
          >
            {approve.isPending || approved
              ? "Approving…"
              : "Approve & build prototype"}
          </Button>
        </div>
      )}
    </div>
  );
}
