import type { FlowType } from "@/types/flow";

/**
 * The stable identifier the backend ships on each ``FlowType`` example —
 * ``name`` is user-facing and may be localized, ``name_key`` is the contract
 * the frontend uses to address a specific starter template.
 *
 * Add new keys here as more quick-templates are wired into the welcome
 * overlay so the call sites stay type-checked instead of stringly-typed.
 */
export type StarterTemplateNameKey = "simple_agent" | "vector_store_rag";

/**
 * Look up a starter-project example by its stable ``name_key``.
 * Returns ``null`` when no example carries the requested key (or when the
 * list is empty / still loading). The caller is responsible for handling
 * the null case — usually by showing a placeholder or skipping the action.
 */
export function findStarterTemplate(
  examples: FlowType[],
  nameKey: StarterTemplateNameKey,
): FlowType | null {
  for (const example of examples) {
    if (example.name_key === nameKey) {
      return example;
    }
  }
  return null;
}
