import type { ProjectConfig, ProjectFlowBindings } from "../../entities";

/** Visibility affects presentation only; switching modes keeps the user's settings. */
export function isProjectFieldVisible(
  field: { show?: boolean; show_when?: Record<string, string> },
  values: ProjectConfig,
): boolean {
  if (field.show === false) return false;
  const bindings = values.flow_bindings as ProjectFlowBindings | undefined;
  return Object.entries(field.show_when ?? {}).every(
    ([name, expected]) => values[name] === expected && !bindings?.[name],
  );
}
