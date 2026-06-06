// The Workspace's right pane. Decides what the canvas shows from the project's
// phase and the `/diagram` endpoint:
//
//   CLARIFICATION              → phase-aware placeholder, no fetch (the diagram
//                                doesn't exist yet and the endpoint is phase-gated)
//   DIAGRAM_GENERATION onward  → fetch /diagram, then:
//       501 (stub)             → NotReady (the canvas backend isn't live yet)
//       other error            → NotReady ("couldn't load")
//       empty diagram          → placeholder ("sketching…")
//       nodes present          → the real <DiagramCanvas>
//
// Contract-first: while /diagram is a 501 stub (Epic 2) every advanced project
// shows NotReady; it "goes live" with no UI change once 2.3 lands.

import type { Project } from "@/controllers/API/queries/lothal";
import { useDiagram } from "@/controllers/API/queries/lothal";
import { CanvasPlaceholder } from "./CanvasPlaceholder";
import { isEmptyDiagram } from "./canvasGraph";
import { DiagramCanvas } from "./DiagramCanvas";
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

export function CanvasSurface({ project }: { project: Project }) {
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
    // NotReady. Anything else is a genuine failure reaching the dockyard.
    return isNotImplemented(error) ? (
      <NotReady title="The canvas isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the diagram"
        detail="Something went wrong reaching the dockyard. Try again in a moment."
      />
    );
  }

  // Endpoint is live but the diagram hasn't been generated yet.
  if (isEmptyDiagram(diagram)) {
    return <CanvasPlaceholder phase={project.phase} />;
  }

  return <DiagramCanvas nodes={diagram!.nodes} edges={diagram!.edges} />;
}
