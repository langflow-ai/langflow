// The Workspace's right pane. Decides what the canvas shows from the project's
// phase and the `/diagram` endpoint:
//
//   CLARIFICATION              → phase-aware placeholder, no fetch (the diagram
//                                doesn't exist yet and the endpoint is phase-gated)
//   DIAGRAM_GENERATION onward  → fetch /diagram, then:
//       501 (stub)             → NotReady (the canvas backend isn't live yet)
//       other error            → NotReady ("couldn't load")
//       no D2 source yet        → placeholder ("sketching…")
//       D2 but no SVG           → NotReady ("couldn't render")
//       SVG present             → the live <D2Canvas>
//
// The diagram artifact is D2 source now (Epic D): the backend renders it to SVG
// on read (D.3/D.6) and we just display that SVG — no D2 compiler in the browser.

import type { Project } from "@/controllers/API/queries/lothal";
import { useDiagram } from "@/controllers/API/queries/lothal";
import { CanvasPlaceholder } from "./CanvasPlaceholder";
import { D2Canvas } from "./D2Canvas";
import type { Anchor } from "./d2/anchor";
import { isNotImplemented, NotReady } from "./NotReady";
import { phaseIndex } from "./phases";

function CanvasLoading() {
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
      Opening the canvas…
    </div>
  );
}

export function CanvasSurface({
  project,
  onAnchor,
}: {
  project: Project;
  /** Forwarded to <D2Canvas>: a double-clicked element drops a chip in the
   *  composer (Epic D.7). */
  onAnchor?: (anchor: Anchor) => void;
}) {
  // The diagram only exists from DIAGRAM_GENERATION onward; before that the
  // endpoint is phase-gated, so we don't even fetch it.
  const hasDiagramPhase = phaseIndex(project.phase) >= 1;
  const {
    data: diagram,
    isLoading,
    isError,
    error,
  } = useDiagram(project.id, hasDiagramPhase);

  if (!hasDiagramPhase) {
    return <CanvasPlaceholder phase={project.phase} />;
  }

  if (isLoading) {
    return <CanvasLoading />;
  }

  if (isError) {
    // A structured 501 means the canvas backend isn't built yet → uniform
    // NotReady. Anything else is a genuine failure reaching the server.
    return isNotImplemented(error) ? (
      <NotReady title="The canvas isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the diagram"
        detail="Something went wrong loading this. Try again in a moment."
      />
    );
  }

  // Endpoint is live but the generator hasn't emitted any D2 yet → still
  // sketching. (`!diagram` also narrows the type for the renders below.)
  if (!diagram || !diagram.d2) {
    return <CanvasPlaceholder phase={project.phase} />;
  }

  // D2 source exists but the backend couldn't render it to SVG (compiler
  // unavailable or render failure — logged server-side). Stored D2 is
  // compile-validated at generation (D.3), so this is an environment fault, not
  // a bad diagram: surface it as NotReady rather than a blank canvas.
  if (!diagram.svg) {
    return (
      <NotReady
        title="Couldn't render the diagram"
        detail="The diagram is ready but couldn't be drawn just now. Try again in a moment."
      />
    );
  }

  return <D2Canvas svg={diagram.svg} onAnchor={onAnchor} />;
}
