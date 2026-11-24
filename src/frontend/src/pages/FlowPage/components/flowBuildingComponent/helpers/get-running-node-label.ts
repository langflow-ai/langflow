/**
 * Produce the label shown in the flow-build status banner for a running node.
 *
 * Extension-bundle components carry a namespaced node id of the form
 * `ext:<bundle>:<ClassName>@<slot>-<uuid>` (the component type is
 * `ext:<bundle>:<ClassName>@<slot>` and `getNodeId` appends `-<uuid>`).
 * Rendering that raw id is verbose and overflows the fixed-width banner, so
 * collapse it to the same `<ComponentName>-<uuid>` shape that built-in
 * components already display. Built-in node ids (e.g. `ChatInput-AbC12`)
 * contain no namespace and are returned unchanged.
 *
 * The namespace-stripping mirrors `classNameFromType` used for output-inspection
 * test ids; here we keep the trailing `-<uuid>` so the banner reads like a
 * built-in component label.
 */
export function getRunningNodeLabel(nodeId: string | undefined): string {
  if (!nodeId) return "";
  const namespacedMatch = nodeId.match(/^ext:[^:]+:([^@]+)@.+-([^-]+)$/);
  if (!namespacedMatch) return nodeId;
  const [, className, uuid] = namespacedMatch;
  return `${className}-${uuid}`;
}
