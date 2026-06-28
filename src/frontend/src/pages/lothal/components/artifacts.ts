// Artifact presentation helpers for the ARCHITECTURE-stage doc-and-diagrams view
// (Epic E.5). The backend emits a flat `{path: content}` artifact map (Epic E.3)
// — `adr.md` plus `diagrams/*.d2`. Here each path becomes a tab: a readable
// label, a kind (the ADR is Markdown; the rest are server-rendered D2 SVGs), and
// a stable order. Keyed off the path, not a hardcoded list, so a future diagram
// (e.g. a deployment diagram, one entry in the backend's DIAGRAM_SPECS) still
// gets a sensible tab with no change here.

export type ArtifactKind = "doc" | "diagram";

export const ADR_PATH = "adr.md";

// Canonical order for the known set — mirrors the backend's DIAGRAM_SPECS order
// (architecture_artifacts.py). The ADR leads; unknown paths sort after it.
const ORDER = [
  ADR_PATH,
  "diagrams/context.d2",
  "diagrams/container.d2",
  "diagrams/data-model.d2",
  "diagrams/sequence.d2",
] as const;

// Curated, readable tab labels for the known set.
const LABELS: Record<string, string> = {
  "adr.md": "Decision Record",
  "diagrams/context.d2": "Context",
  "diagrams/container.d2": "Container",
  "diagrams/data-model.d2": "Data Model",
  "diagrams/sequence.d2": "Sequence",
};

/** Whether an artifact is a renderable D2 diagram (`diagrams/*.d2`) or a doc. */
export function artifactKind(path: string): ArtifactKind {
  return path.startsWith("diagrams/") && path.endsWith(".d2")
    ? "diagram"
    : "doc";
}

// A readable tab label. Known paths get a curated name; anything else derives
// one from its filename so a future artifact still reads sensibly
// ("diagrams/event-flow.d2" → "Event Flow").
export function artifactLabel(path: string): string {
  if (LABELS[path]) return LABELS[path];
  const base = path.split("/").pop() ?? path;
  const stem = base.replace(/\.[^.]+$/, "");
  return (
    stem
      .split(/[-_]/)
      .filter(Boolean)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ") || path
  );
}

export type ArtifactTab = {
  path: string;
  label: string;
  kind: ArtifactKind;
};

// Order an artifact map's keys into tabs: the known set first in canonical
// order, then any unknown paths alphabetically.
export function orderArtifacts(paths: string[]): ArtifactTab[] {
  const rank = (p: string) => {
    const i = ORDER.indexOf(p as (typeof ORDER)[number]);
    return i === -1 ? ORDER.length : i;
  };
  return [...paths]
    .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
    .map((path) => ({
      path,
      label: artifactLabel(path),
      kind: artifactKind(path),
    }));
}
