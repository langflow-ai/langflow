import { ENABLE_KNOWLEDGE_BASES } from "@/customization/feature-flags";
import type { FlowType } from "@/types/flow";

/** Tab that lists every template, rather than one tag's worth. */
export const ALL_TEMPLATES_TAB = "all-templates";

/** Tab holding the three hand-picked cards. */
export const GET_STARTED_TAB = "get-started";

/**
 * The templates the Get started cards are built from, in card order.
 *
 * A catalog policy can block any of them, so this is also what decides
 * whether that tab has anything left to show.
 */
export const FEATURED_TEMPLATE_KEYS = [
  "basic_prompting",
  "vector_store_rag",
  "simple_agent",
] as const;

/** Whether a template is listed at all, before any tab narrows it further. */
export function isTemplateVisible(example: FlowType): boolean {
  return ENABLE_KNOWLEDGE_BASES || !example.name?.includes("Knowledge");
}

/**
 * The tab ids that still have at least one template behind them.
 *
 * An administrator's catalog policy can empty any tab — or all of them — so
 * the nav needs this to avoid offering a destination with nothing in it.
 */
export function availableTemplateTabs(
  examples: readonly FlowType[],
): ReadonlySet<string> {
  const visible = examples.filter(isTemplateVisible);
  const tabs = new Set<string>();

  if (visible.length > 0) {
    tabs.add(ALL_TEMPLATES_TAB);
  }
  if (
    visible.some((example) =>
      FEATURED_TEMPLATE_KEYS.some((key) => key === example.name_key),
    )
  ) {
    tabs.add(GET_STARTED_TAB);
  }
  for (const example of visible) {
    for (const tag of example.tags ?? []) {
      tabs.add(tag);
    }
  }
  return tabs;
}
