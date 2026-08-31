import { useMemo } from "react";
import type { APIDataType } from "@/types/api";
import { applyBetaFilter } from "../helpers/apply-beta-filter";
import { applyComponentFilter } from "../helpers/apply-component-filter";
import { applyEdgeFilter } from "../helpers/apply-edge-filter";
import { applyLegacyFilter } from "../helpers/apply-legacy-filter";

interface EdgeFilter {
  family: string;
  type: string;
}

export interface UseSidebarFiltersParams {
  searchFilteredData: APIDataType;
  getFilterEdge: EdgeFilter[];
  getFilterComponent: string;
  showBeta: boolean;
  showLegacy: boolean;
}

/**
 * Applies the sidebar's four filter stages IN ORDER (edge → component → beta →
 * legacy) over the search-filtered data. Order preserved verbatim from
 * FlowSidebarComponent (LE-1736 W35).
 */
export function useSidebarFilters({
  searchFilteredData,
  getFilterEdge,
  getFilterComponent,
  showBeta,
  showLegacy,
}: UseSidebarFiltersParams): APIDataType {
  return useMemo(() => {
    let filteredData = searchFilteredData;

    if (getFilterEdge?.length > 0) {
      filteredData = applyEdgeFilter(filteredData, getFilterEdge);
    }

    if (getFilterComponent !== "") {
      filteredData = applyComponentFilter(filteredData, getFilterComponent);
    }

    if (!showBeta) {
      filteredData = applyBetaFilter(filteredData);
    }

    if (!showLegacy) {
      filteredData = applyLegacyFilter(filteredData);
    }

    return filteredData;
  }, [
    searchFilteredData,
    getFilterEdge,
    getFilterComponent,
    showBeta,
    showLegacy,
  ]);
}
