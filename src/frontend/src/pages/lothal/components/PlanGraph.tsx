// PLAN stage — the dependency-graph view. Shows the server-rendered DAG SVG (from
// the PM service via the bridge) plus the dependency links: a list and, while the
// project is editable, an add-link form. The same native-shell surface as the tree
// view; no iframe.

import DOMPurify from "dompurify";
import { useMemo, useState } from "react";
import {
  type PlanLink,
  type PlanLinkType,
  type PlanNode,
  useCreatePlanLink,
  usePlanDag,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { EmptyHint } from "./EmptyHint";

const LINK_TYPES: PlanLinkType[] = [
  "derives_from",
  "blocks",
  "blocked_by",
  "relates_to",
  "verifies",
];

const selectStyle = {
  fontSize: 12,
  padding: "6px 8px",
  border: "1px solid var(--border)",
  borderRadius: 8,
  background: "var(--paper)",
  color: "var(--ink)",
  minWidth: 0,
};

export function PlanGraph({
  projectId,
  nodes,
  links,
  editable,
}: {
  projectId: string;
  nodes: PlanNode[];
  links: PlanLink[];
  editable: boolean;
}) {
  const { data: svg, isLoading, error } = usePlanDag(projectId);
  const createLink = useCreatePlanLink(projectId);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [type, setType] = useState<PlanLinkType>("derives_from");

  // The SVG comes from our own PM service (d2), but treat it as untrusted before
  // injecting it (defence-in-depth, mirroring D2Canvas): sanitize to the SVG
  // profile and drop the script / foreignObject vectors. It carries no root
  // width/height, so we also force it to scale to the pane width.
  const safeSvg = useMemo(
    () =>
      svg
        ? DOMPurify.sanitize(svg, {
            USE_PROFILES: { svg: true, svgFilters: true },
            FORBID_TAGS: ["script", "foreignObject"],
          }).replace(
            "<svg ",
            '<svg style="width:100%;height:auto;display:block" ',
          )
        : "",
    [svg],
  );

  const nameOf = (id: string) => nodes.find((n) => n.id === id)?.name ?? id.slice(0, 8);

  const addLink = () => {
    if (!source || !target || source === target || createLink.isPending) return;
    createLink.mutate(
      { source_id: source, target_id: target, link_type: type },
      { onSuccess: () => { setSource(""); setTarget(""); } },
    );
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "auto",
          padding: 20,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {isLoading ? (
          <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>
            Rendering graph…
          </span>
        ) : error ? (
          <EmptyHint
            title="Couldn't render the graph"
            sub="The dependency graph failed to load — the planning service may be unavailable. Try again in a moment."
          />
        ) : safeSvg ? (
          // Sanitized server-rendered d2 SVG (see `safeSvg`), shown on a light
          // card because d2 uses its own palette and emits no root width/height.
          <div
            style={{
              background: "#fbfbfd",
              borderRadius: 12,
              padding: 18,
              width: "min(100%, 760px)",
              maxHeight: "100%",
              overflow: "auto",
              boxShadow: "0 1px 0 var(--border)",
            }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: safeSvg }}
          />
        ) : (
          <EmptyHint
            title="No graph yet"
            sub="Add nodes and dependency links to see the DAG."
          />
        )}
      </div>

      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "10px 14px",
          maxHeight: 230,
          overflowY: "auto",
          background: "var(--surface)",
        }}
      >
        <span
          style={{
            fontSize: 9.5,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "var(--ink-mute)",
          }}
        >
          Dependency links · {links.length}
        </span>
        <div style={{ marginTop: 6 }}>
          {links.length === 0 ? (
            <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>
              No links yet.
            </span>
          ) : (
            links.map((l) => (
              <div
                key={l.id}
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  padding: "4px 0",
                  fontSize: 12.5,
                }}
              >
                <span>{nameOf(l.source_id)}</span>
                <span style={{ color: "var(--ink-mute)", fontSize: 11 }}>
                  —{l.link_type}→
                </span>
                <span>{nameOf(l.target_id)}</span>
              </div>
            ))
          )}
        </div>

        {editable && nodes.length >= 2 && (
          <div style={{ display: "flex", gap: 6, marginTop: 10, alignItems: "center" }}>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">source…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as PlanLinkType)}
              style={selectStyle}
            >
              {LINK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">target…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              size="sm"
              disabled={
                !source || !target || source === target || createLink.isPending
              }
              onClick={addLink}
            >
              Link
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
