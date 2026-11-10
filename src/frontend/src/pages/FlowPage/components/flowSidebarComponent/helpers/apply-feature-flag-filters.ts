import { cloneDeep } from "lodash";
import type { APIClassType, APIDataType } from "@/types/api";
import { hideConnectionBackedComponents } from "@/utils/connection-ref-gate";

export interface FeatureFlagFilterOptions {
  enableKnowledgeBases: boolean;
  enableIntegrations: boolean;
  enableTriggers: boolean;
}

/** Palette category holding the core trigger components (Schedule, ...). */
export const TRIGGERS_CATEGORY = "triggers";

/**
 * True for a trigger node, wherever the palette lists it. Core triggers sit in
 * the Triggers category, but a provider's triggers (Slack: On Message) sit in
 * that provider's group next to its actions; the server stamps every one of
 * them with `metadata.trigger_kind` from the loaded class.
 */
export function isTriggerComponent(
  component: APIClassType | undefined,
): boolean {
  // `metadata` is an object, which APIClassType's index signature does not
  // admit, so it is read through this one narrow view rather than widening the
  // palette type for every consumer.
  const metadata = (component as ComponentMetadataView | undefined)?.metadata;
  return typeof metadata?.trigger_kind === "string";
}

type ComponentMetadataView = { metadata?: { trigger_kind?: unknown } };

/**
 * Removes the Triggers category and every trigger-marked component from the
 * other categories. Categories without a trigger keep their identity, and a
 * category that held nothing but triggers is dropped.
 */
function hideTriggers(data: APIDataType): APIDataType {
  let changed = false;
  const kept: [string, APIDataType[string]][] = [];
  for (const [category, components] of Object.entries(data)) {
    if (category === TRIGGERS_CATEGORY) {
      changed = true;
      continue;
    }
    const remaining = Object.entries(components).filter(
      ([, component]) => !isTriggerComponent(component),
    );
    if (remaining.length === Object.keys(components).length) {
      kept.push([category, components]);
      continue;
    }
    changed = true;
    if (remaining.length > 0) {
      kept.push([category, Object.fromEntries(remaining)]);
    }
  }
  return changed ? Object.fromEntries(kept) : data;
}

/**
 * Removes components whose feature is switched off from the palette data.
 * Search, categories and bundles all derive from the result.
 */
export function applyFeatureFlagFilters(
  rawData: APIDataType,
  {
    enableKnowledgeBases,
    enableIntegrations,
    enableTriggers,
  }: FeatureFlagFilterOptions,
): APIDataType {
  // With integrations off there is no connection picker, so a connection-backed
  // component could never be configured: keep it out of the palette.
  const integrationData = enableIntegrations
    ? rawData
    : hideConnectionBackedComponents(rawData);

  // With triggers off there is no control to arm a trigger node, so one dropped
  // on the canvas would sit in `pending` forever: keep every trigger out, the
  // Triggers category and the provider triggers listed in their own groups.
  const paletteData = enableTriggers
    ? integrationData
    : hideTriggers(integrationData);

  if (enableKnowledgeBases) {
    return paletteData;
  }

  const knowledgeComponentNames = ["KnowledgeBase"];

  // Create a deep copy to avoid mutating the original
  const filteredData = cloneDeep(paletteData);

  if (filteredData.files_and_knowledge) {
    // Filter out knowledge components by creating a new object without them
    const filteredCategory = Object.fromEntries(
      Object.entries(filteredData.files_and_knowledge).filter(
        ([componentName]) => !knowledgeComponentNames.includes(componentName),
      ),
    );

    filteredData.files_and_knowledge = filteredCategory;
  }

  return filteredData;
}
