import { cloneDeep } from "lodash";
import type { APIDataType } from "@/types/api";
import { hideConnectionBackedComponents } from "@/utils/connection-ref-gate";

export interface FeatureFlagFilterOptions {
  enableKnowledgeBases: boolean;
  enableIntegrations: boolean;
}

/**
 * Removes components whose feature is switched off from the palette data.
 * Search, categories and bundles all derive from the result.
 */
export function applyFeatureFlagFilters(
  rawData: APIDataType,
  { enableKnowledgeBases, enableIntegrations }: FeatureFlagFilterOptions,
): APIDataType {
  // Connection-backed components have no connection_ref renderer until INT-8
  const paletteData = enableIntegrations
    ? rawData
    : hideConnectionBackedComponents(rawData);

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
