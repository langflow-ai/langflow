import { cloneDeep } from "lodash";
import type { APIDataType } from "@/types/api";
import { hideConnectionBackedComponents } from "@/utils/connection-ref-gate";

export interface FeatureFlagFilterOptions {
  enableKnowledgeBases: boolean;
  enableIntegrations: boolean;
  enableTriggers: boolean;
}

/** Palette category holding the trigger components (Schedule, ...). */
export const TRIGGERS_CATEGORY = "triggers";

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
  // on the canvas would sit in `pending` forever: keep the category out.
  const paletteData =
    enableTriggers || !(TRIGGERS_CATEGORY in integrationData)
      ? integrationData
      : Object.fromEntries(
          Object.entries(integrationData).filter(
            ([category]) => category !== TRIGGERS_CATEGORY,
          ),
        );

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
