import type { ProjectConfig } from "../../entities";

/** Visibility affects presentation only; switching modes keeps the user's settings. */
export function isProjectFieldVisible(
  field: { show?: boolean; show_when?: Record<string, string> },
  values: ProjectConfig,
): boolean {
  if (field.show === false) return false;
  return Object.entries(field.show_when ?? {}).every(
    ([name, expected]) => values[name] === expected,
  );
}
