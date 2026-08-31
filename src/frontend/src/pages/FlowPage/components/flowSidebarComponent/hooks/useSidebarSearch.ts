import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import { useEffect, useMemo, useState } from "react";
import type { APIClassType, APIDataType } from "@/types/api";
import type { MCPServerInfoType } from "@/types/mcp";
import { combinedResultsFn } from "../helpers/combined-results";
import { filteredDataFn } from "../helpers/filtered-data";
import { normalizeString } from "../helpers/normalize-string";
import { traditionalSearchMetadata } from "../helpers/traditional-search-metadata";

export const MCP_COMPONENT_CATEGORY = "models_and_agents";

export type SidebarSearchItem = APIClassType & {
  category: string;
  key: string;
  mcpServerName?: string;
};

export interface UseSidebarSearchParams {
  baseData: APIDataType;
  debouncedSearch: string;
  data: APIDataType;
  mcpServers: MCPServerInfoType[] | undefined;
  mcpSuccess: boolean;
}

/**
 * Owns the sidebar's Fuse index (rebuilt from baseData) plus the derived search
 * results / search-filtered data and the mcpSearchData used for non-search
 * display. Extracted verbatim from FlowSidebarComponent (LE-1736 W34).
 */
export function useSidebarSearch({
  baseData,
  debouncedSearch,
  data,
  mcpServers,
  mcpSuccess,
}: UseSidebarSearchParams) {
  const [fuse, setFuse] = useState<Fuse<SidebarSearchItem> | null>(null);
  const [mcpSearchData, setMcpSearchData] = useState<SidebarSearchItem[]>([]);

  const searchResults = useMemo(() => {
    if (!debouncedSearch || !fuse) return null;

    const searchTerm = normalizeString(debouncedSearch);
    const fuseResults = fuse.search(debouncedSearch).map((result) => ({
      ...result,
      item: { ...result.item, score: result.score },
    }));

    const fuseCategories = fuseResults.map((result) => result.item.category);
    const combinedResults = combinedResultsFn(fuseResults, baseData);
    const traditionalResults = traditionalSearchMetadata(baseData, searchTerm);

    return {
      fuseResults,
      fuseCategories,
      combinedResults,
      traditionalResults,
    };
  }, [debouncedSearch, fuse, baseData]);

  const searchFilteredData = useMemo(() => {
    if (!debouncedSearch || !searchResults) return cloneDeep(baseData);

    const filteredData = filteredDataFn(
      baseData,
      searchResults.combinedResults,
      searchResults.traditionalResults,
    );

    return filteredData;
  }, [baseData, debouncedSearch, searchResults]);

  useEffect(() => {
    const options = {
      keys: [
        "display_name",
        "description",
        "type",
        "category",
        "mcpServerName",
      ],
      threshold: 0.2,
      includeScore: true,
    };

    const fuseData: SidebarSearchItem[] = Object.entries(baseData).flatMap(
      ([category, items]) =>
        Object.entries(items).map(([key, value]) => ({
          ...value,
          category,
          key,
        })),
    );

    // MCP data is already included in baseData, but we still need mcpSearchData for non-search display
    if (
      mcpSuccess &&
      mcpServers &&
      data[MCP_COMPONENT_CATEGORY]?.["MCPTools"]
    ) {
      const mcpComponent = data[MCP_COMPONENT_CATEGORY]["MCPTools"];
      const newMcpSearchData = mcpServers.map((mcpServer) => ({
        ...mcpComponent,
        mcpServerName: mcpServer.name, // adds this field and makes it searchable
        category: "MCP",
        key: `mcp_${mcpServer.name}`,
        template: {
          ...mcpComponent.template,
          mcp_server: {
            ...mcpComponent.template.mcp_server,
            value: mcpServer,
          },
        },
      }));

      setMcpSearchData(newMcpSearchData);
      // No need to push to fuseData since it's already in baseData
    } else {
      setMcpSearchData([]);
    }
    setFuse(new Fuse(fuseData, options));
  }, [baseData, mcpSuccess, mcpServers]);

  return { searchResults, searchFilteredData, mcpSearchData };
}
