import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import {
  createContext,
  memo,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShallow } from "zustand/react/shallow";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarInset,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import SkeletonGroup from "@/components/ui/skeletonGroup";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { ENABLE_API, ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useAddComponent } from "@/hooks/use-add-component";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useStoreStore } from "@/stores/storeStore";
import { checkChatInput, checkWebhookInput } from "@/utils/reactflowUtils";
import {
  nodeColors,
  SIDEBAR_BUNDLES,
  SIDEBAR_CATEGORIES,
} from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import type { APIClassType } from "../../../../types/api";
import isWrappedWithClass from "../PageComponent/utils/is-wrapped-with-class";
import { CategoryGroup } from "./components/categoryGroup";
import NoResultsMessage from "./components/emptySearchComponent";
import McpSidebarGroup from "./components/McpSidebarGroup";
import MemoizedSidebarGroup from "./components/sidebarBundles";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
import { SidebarHeaderComponent } from "./components/sidebarHeader";
import SidebarSegmentedNav from "./components/sidebarSegmentedNav";
import { applyBetaFilter } from "./helpers/apply-beta-filter";
import { applyEdgeFilter } from "./helpers/apply-edge-filter";
import { applyLegacyFilter } from "./helpers/apply-legacy-filter";
import { combinedResultsFn } from "./helpers/combined-results";
import { filteredDataFn } from "./helpers/filtered-data";
import { normalizeString } from "./helpers/normalize-string";
import sensitiveSort from "./helpers/sensitive-sort";
import { traditionalSearchMetadata } from "./helpers/traditional-search-metadata";
import { UniqueInputsComponents } from "./types";

const CATEGORIES = SIDEBAR_CATEGORIES;
const BUNDLES = SIDEBAR_BUNDLES;

// Search context for the sidebar
export type SearchContextType = {
  focusSearch: () => void;
  isSearchFocused: boolean;
  // Additional properties for the sidebar to use
  search?: string;
  setSearch?: (value: string) => void;
  searchInputRef?: React.RefObject<HTMLInputElement>;
  handleInputFocus?: () => void;
  handleInputBlur?: () => void;
  handleInputChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
};

export const SearchContext = createContext<SearchContextType | null>(null);

export function useSearchContext() {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error("useSearchContext must be used within SearchProvider");
  }
  return context;
}

interface SearchProviderProps {
  children: React.ReactNode;
  searchInputRef: React.RefObject<HTMLInputElement>;
  isSearchFocused: boolean;
}

// Create a provider that can be used at the FlowPage level
export function FlowSearchProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [search, setSearch] = useState("");
  const [isInputFocused, setIsInputFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const focusSearchInput = useCallback(() => {
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, []);

  const handleInputFocus = useCallback(() => {
    setIsInputFocused(true);
  }, []);

  const handleInputBlur = useCallback(() => {
    setIsInputFocused(false);
  }, []);

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setSearch(event.target.value);
    },
    [],
  );

  const searchContextValue = useMemo(
    () => ({
      focusSearch: focusSearchInput,
      isSearchFocused: isInputFocused,
      // Also expose the search state and handlers for the sidebar to use
      search,
      setSearch,
      searchInputRef,
      handleInputFocus,
      handleInputBlur,
      handleInputChange,
    }),
    [
      focusSearchInput,
      isInputFocused,
      search,
      handleInputFocus,
      handleInputBlur,
      handleInputChange,
    ],
  );

  return (
    <SearchContext.Provider value={searchContextValue}>
      {children}
    </SearchContext.Provider>
  );
}

interface FlowSidebarComponentProps {
  isLoading?: boolean;
  showLegacy?: boolean;
  setShowLegacy?: (value: boolean) => void;
}

export function FlowSidebarComponent({ isLoading }: FlowSidebarComponentProps) {
  const data = useTypesStore((state) => state.data);

  const { getFilterEdge, setFilterEdge, filterType } = useFlowStore(
    useShallow((state) => ({
      getFilterEdge: state.getFilterEdge,
      setFilterEdge: state.setFilterEdge,
      filterType: state.filterType,
    })),
  );

  const hasStore = useStoreStore((state) => state.hasStore);
  const { setOpen } = useSidebar();
  const addComponent = useAddComponent();

  // Get MCP servers for search functionality (only when new sidebar is enabled)
  const {
    data: mcpServers,
    isLoading: mcpLoading,
    isSuccess: mcpSuccess,
    isError: mcpError,
  } = useGetMCPServers({ enabled: ENABLE_NEW_SIDEBAR });

  // Get search state from context
  const context = useSearchContext();
  const {
    search = "",
    setSearch = () => {},
    searchInputRef = useRef<HTMLInputElement | null>(null),
    isSearchFocused = false,
    handleInputFocus = () => {},
    handleInputBlur = () => {},
    handleInputChange = () => {},
    focusSearch = () => {},
  } = context;

  // State
  const [fuse, setFuse] = useState<Fuse<any> | null>(null);
  const [openCategories, setOpenCategories] = useState<string[]>([]);
  const [showConfig, setShowConfig] = useState(false);
  const [showBeta, setShowBeta] = useState(true);
  const [showLegacy, setShowLegacy] = useState(false);
  const [mcpSearchData, setMcpSearchData] = useState<any[]>([]);

  // Create base data that includes MCP category when available
  const baseData = useMemo(() => {
    if (mcpSuccess && mcpServers && data["agents"]?.["MCPTools"]) {
      const mcpComponent = data["agents"]["MCPTools"];
      const newMcpSearchData = mcpServers.map((mcpServer) => ({
        ...mcpComponent,
        display_name: mcpServer.name,
        description: `MCP Server: ${mcpServer.name}`,
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

      const mcpCategoryData: Record<string, any> = {};
      newMcpSearchData.forEach((mcp) => {
        mcpCategoryData[mcp.display_name] = mcp;
      });

      return {
        ...data,
        MCP: mcpCategoryData,
      };
    }
    return data;
  }, [data, mcpSuccess, mcpServers]);

  const [dataFilter, setFilterData] = useState(baseData);

  const customComponent = useMemo(() => {
    return data?.["custom_component"]?.["CustomComponent"] ?? null;
  }, [data]);

  const searchResults = useMemo(() => {
    if (!search || !fuse) return null;

    const searchTerm = normalizeString(search);
    const fuseResults = fuse.search(search).map((result) => ({
      ...result,
      item: { ...result.item, score: result.score },
    }));

    // Debug logging for search
    console.log("Search term:", search);
    console.log("Fuse results:", fuseResults);
    console.log(
      "MCP results:",
      fuseResults.filter((r) => r.item.category === "MCP"),
    );

    const fuseCategories = fuseResults.map((result) => result.item.category);
    const combinedResults = combinedResultsFn(fuseResults, baseData);
    const traditionalResults = traditionalSearchMetadata(baseData, searchTerm);

    console.log("Fuse categories:", fuseCategories);
    console.log("Combined results:", combinedResults);
    console.log("Traditional results:", traditionalResults);

    return {
      fuseResults,
      fuseCategories,
      combinedResults,
      traditionalResults,
    };
  }, [search, fuse, baseData]);

  const searchFilteredData = useMemo(() => {
    if (!search || !searchResults) return cloneDeep(baseData);

    const filteredData = filteredDataFn(
      baseData,
      searchResults.combinedResults,
      searchResults.traditionalResults,
    );

    console.log("Original baseData keys:", Object.keys(baseData));
    console.log("Search filtered data:", filteredData);
    console.log(
      "MCP in filtered data:",
      filteredData["MCP"] || "No MCP category found",
    );

    return filteredData;
  }, [baseData, search, searchResults]);

  const sortedCategories = useMemo(() => {
    if (!searchResults || !searchFilteredData) return [];

    return Object.keys(searchFilteredData).toSorted((a, b) =>
      searchResults.fuseCategories.indexOf(b) <
      searchResults.fuseCategories.indexOf(a)
        ? 1
        : -1,
    );
  }, [searchResults, searchFilteredData, CATEGORIES, BUNDLES]);

  const finalFilteredData = useMemo(() => {
    let filteredData = searchFilteredData;

    if (getFilterEdge?.length > 0) {
      filteredData = applyEdgeFilter(filteredData, getFilterEdge);
    }

    if (!showBeta) {
      filteredData = applyBetaFilter(filteredData);
    }

    if (!showLegacy) {
      filteredData = applyLegacyFilter(filteredData);
    }

    return filteredData;
  }, [searchFilteredData, getFilterEdge, showBeta, showLegacy]);

  const hasResults = useMemo(() => {
    console.log("dataFilter", dataFilter);
    return Object.entries(dataFilter).some(
      ([category, items]) =>
        (Object.keys(items).length > 0 &&
          (CATEGORIES.find((c) => c.name === category) ||
            BUNDLES.find((b) => b.name === category))) ||
        category === "MCP",
    );
  }, [dataFilter]);

  const handleKeyDownInput = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>, name: string) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpenCategories((prev) =>
          prev.includes(name)
            ? prev.filter((cat) => cat !== name)
            : [...prev, name],
        );
      }
    },
    [],
  );

  const handleClearSearch = useCallback(() => {
    setSearch("");
    setFilterData(baseData);
    setOpenCategories([]);
  }, [baseData, setSearch]);

  useEffect(() => {
    if (filterType) {
      setOpen(true);
    }
  }, [filterType, setOpen]);

  useEffect(() => {
    setFilterData(finalFilteredData);

    if (search !== "" || filterType || getFilterEdge.length > 0) {
      const newOpenCategories = Object.keys(finalFilteredData).filter(
        (cat) => Object.keys(finalFilteredData[cat]).length > 0,
      );
      setOpenCategories(newOpenCategories);
    }
  }, [finalFilteredData, search, filterType, getFilterEdge]);

  // Update dataFilter when baseData changes
  useEffect(() => {
    setFilterData(baseData);
  }, [baseData]);

  useEffect(() => {
    const options = {
      keys: ["display_name", "description", "type", "category"],
      threshold: 0.4, // More lenient threshold for better partial matching
      includeScore: true,
      // Add more fuzzy search options
      location: 0, // Start searching from the beginning of strings
      distance: 100, // How far to search
    };

    const fuseData = Object.entries(baseData).flatMap(([category, items]) =>
      Object.entries(items).map(([key, value]) => ({
        ...value,
        category,
        key,
      })),
    );

    // MCP data is already included in baseData, but we still need mcpSearchData for non-search display
    if (mcpSuccess && mcpServers && data["agents"]?.["MCPTools"]) {
      const mcpComponent = data["agents"]["MCPTools"];
      const newMcpSearchData = mcpServers.map((mcpServer) => ({
        ...mcpComponent,
        display_name: mcpServer.name,
        description: `MCP Server: ${mcpServer.name}`,
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

    console.log("fuseData", fuseData);
    setFuse(new Fuse(fuseData, options));
  }, [baseData, mcpSuccess, mcpServers]);

  useEffect(() => {
    if (getFilterEdge.length !== 0) {
      setSearch("");
    }
  }, [getFilterEdge, baseData]);

  useEffect(() => {
    if (search === "" && getFilterEdge.length === 0) {
      setOpenCategories([]);
    }
  }, [search, getFilterEdge]);

  const searchComponentsSidebar = useShortcutsStore(
    (state) => state.searchComponentsSidebar,
  );

  useHotkeys(
    searchComponentsSidebar,
    (e: KeyboardEvent) => {
      if (isWrappedWithClass(e, "noflow")) return;
      e.preventDefault();
      searchInputRef.current?.focus();
      setOpen(true);
    },
    {
      preventDefault: true,
    },
  );

  useHotkeys(
    "esc",
    (event) => {
      event.preventDefault();
      searchInputRef.current?.blur();
    },
    {
      enableOnFormTags: true,
      enabled: isSearchFocused,
    },
  );

  const onDragStart = useCallback(
    (
      event: React.DragEvent<any>,
      data: { type: string; node?: APIClassType },
    ) => {
      var crt = event.currentTarget.cloneNode(true);
      crt.style.position = "absolute";
      crt.style.width = "215px";
      crt.style.top = "-500px";
      crt.style.right = "-500px";
      crt.classList.add("cursor-grabbing");
      document.body.appendChild(crt);
      event.dataTransfer.setDragImage(crt, 0, 0);
      event.dataTransfer.setData("genericNode", JSON.stringify(data));
    },
    [],
  );

  const hasCoreComponents = useMemo(() => {
    const categoriesWithItems = CATEGORIES.filter(
      (item) =>
        dataFilter[item.name] && Object.keys(dataFilter[item.name]).length > 0,
    );
    const result = categoriesWithItems.length > 0;
    console.log("hasCoreComponents check:");
    console.log(
      "  CATEGORIES names:",
      CATEGORIES.map((c) => c.name),
    );
    console.log(
      "  categories with items:",
      categoriesWithItems.map((c) => c.name),
    );
    console.log(
      "  category item counts:",
      CATEGORIES.map((c) => ({
        name: c.name,
        hasData: !!dataFilter[c.name],
        count: dataFilter[c.name] ? Object.keys(dataFilter[c.name]).length : 0,
      })),
    );
    console.log("  result:", result);
    return result;
  }, [dataFilter]);

  const hasBundleItems = useMemo(() => {
    const bundlesWithItems = BUNDLES.filter(
      (item) =>
        dataFilter[item.name] && Object.keys(dataFilter[item.name]).length > 0,
    );
    const result = bundlesWithItems.length > 0;
    console.log("hasBundleItems check:");
    console.log(
      "  BUNDLES names:",
      BUNDLES.map((b) => b.name),
    );
    console.log(
      "  bundles with items:",
      bundlesWithItems.map((b) => b.name),
    );
    console.log(
      "  bundle item counts:",
      BUNDLES.map((b) => ({
        name: b.name,
        hasData: !!dataFilter[b.name],
        count: dataFilter[b.name] ? Object.keys(dataFilter[b.name]).length : 0,
      })),
    );
    console.log("  result:", result);
    return result;
  }, [dataFilter]);

  const { activeSection } = useSidebar();

  const hasMcpServers = Boolean(mcpServers && mcpServers.length > 0);

  const showComponents =
    (ENABLE_NEW_SIDEBAR &&
      hasCoreComponents &&
      (activeSection === "components" || activeSection === "search")) ||
    (search !== "" && hasCoreComponents && ENABLE_NEW_SIDEBAR) ||
    !ENABLE_NEW_SIDEBAR;
  const showBundles =
    (hasBundleItems && ENABLE_NEW_SIDEBAR && activeSection === "bundles") ||
    (search !== "" && hasBundleItems && ENABLE_NEW_SIDEBAR) ||
    !ENABLE_NEW_SIDEBAR;
  const showMcp =
    (ENABLE_NEW_SIDEBAR && activeSection === "mcp") ||
    (search !== "" && dataFilter["MCP"].length > 0 && ENABLE_NEW_SIDEBAR);

  return (
    <Sidebar
      collapsible={"offcanvas"}
      data-testid="shad-sidebar"
      className="noflow select-none"
    >
      <div className="flex h-full">
        {ENABLE_NEW_SIDEBAR && <SidebarSegmentedNav />}
        <div
          className={cn(
            "flex flex-col h-full w-full group-data-[collapsible=icon]:hidden",
            ENABLE_NEW_SIDEBAR && "sidebar-segmented",
          )}
        >
          <SidebarHeaderComponent
            showConfig={showConfig}
            setShowConfig={setShowConfig}
            showBeta={showBeta}
            setShowBeta={setShowBeta}
            showLegacy={showLegacy}
            setShowLegacy={setShowLegacy}
            searchInputRef={searchInputRef}
            isInputFocused={isSearchFocused}
            search={search}
            handleInputFocus={handleInputFocus}
            handleInputBlur={handleInputBlur}
            handleInputChange={handleInputChange}
            filterType={filterType}
            setFilterEdge={setFilterEdge}
            setFilterData={setFilterData}
            data={data}
          />

          <SidebarContent
            segmentedSidebar={ENABLE_NEW_SIDEBAR}
            className="flex-1 group-data-[collapsible=icon]:hidden"
          >
            {isLoading ? (
              <div className="flex flex-col gap-2">
                <div className="flex flex-col gap-1 p-3">
                  <SkeletonGroup count={13} className="my-0.5 h-7" />
                </div>
                <div className="h-8" />
                <div className="flex flex-col gap-1 px-3 pt-2">
                  <SkeletonGroup count={21} className="my-0.5 h-7" />
                </div>
              </div>
            ) : (
              <>
                {hasResults ? (
                  <>
                    {showComponents && (
                      <CategoryGroup
                        dataFilter={dataFilter}
                        sortedCategories={sortedCategories}
                        CATEGORIES={CATEGORIES}
                        openCategories={openCategories}
                        setOpenCategories={setOpenCategories}
                        search={search}
                        nodeColors={nodeColors}
                        onDragStart={onDragStart}
                        sensitiveSort={sensitiveSort}
                        showConfig={showConfig}
                        setShowConfig={setShowConfig}
                      />
                    )}
                    {showMcp && (
                      <McpSidebarGroup
                        mcpComponents={
                          search !== ""
                            ? Object.values(dataFilter["MCP"] || {})
                            : mcpSearchData
                        }
                        nodeColors={nodeColors}
                        onDragStart={onDragStart}
                        openCategories={openCategories}
                        setOpenCategories={setOpenCategories}
                        mcpServers={mcpServers}
                        mcpLoading={mcpLoading}
                        mcpSuccess={mcpSuccess}
                        mcpError={mcpError}
                        search={search}
                        hasMcpServers={hasMcpServers}
                      />
                    )}
                    {showBundles && (
                      <MemoizedSidebarGroup
                        BUNDLES={BUNDLES}
                        search={search}
                        sortedCategories={sortedCategories}
                        dataFilter={dataFilter}
                        nodeColors={nodeColors}
                        onDragStart={onDragStart}
                        sensitiveSort={sensitiveSort}
                        openCategories={openCategories}
                        setOpenCategories={setOpenCategories}
                        handleKeyDownInput={handleKeyDownInput}
                      />
                    )}
                  </>
                ) : (
                  <NoResultsMessage onClearSearch={handleClearSearch} />
                )}
              </>
            )}
          </SidebarContent>
          {ENABLE_NEW_SIDEBAR &&
          activeSection === "mcp" &&
          !hasMcpServers ? null : (
            <SidebarFooter className="border-t p-4 py-3 group-data-[collapsible=icon]:hidden">
              <SidebarMenuButtons
                customComponent={customComponent}
                addComponent={addComponent}
                isLoading={isLoading}
              />
            </SidebarFooter>
          )}
        </div>
      </div>
    </Sidebar>
  );
}

FlowSidebarComponent.displayName = "FlowSidebarComponent";

export default memo(
  FlowSidebarComponent,
  (
    prevProps: FlowSidebarComponentProps,
    nextProps: FlowSidebarComponentProps,
  ) => {
    return (
      prevProps.showLegacy === nextProps.showLegacy &&
      prevProps.setShowLegacy === nextProps.setShowLegacy
    );
  },
);
