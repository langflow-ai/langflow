import { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import SkeletonGroup from "@/components/ui/skeletonGroup";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import {
  ENABLE_KNOWLEDGE_BASES,
  ENABLE_NEW_SIDEBAR,
} from "@/customization/feature-flags";
import { useAddComponent } from "@/hooks/use-add-component";
import { useUtilityStore } from "@/stores/utilityStore";
import { setLocalStorage } from "@/utils/local-storage-util";
import {
  nodeColors,
  SIDEBAR_BUNDLES,
  SIDEBAR_CATEGORIES,
} from "@/utils/styleUtils";
import { cn, getBooleanFromStorage } from "@/utils/utils";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import type { APIClassType } from "../../../../types/api";
import { CategoryGroup } from "./components/categoryGroup";
import NoResultsMessage from "./components/emptySearchComponent";
import FlowVersionSidebarContent from "./components/FlowVersionSidebarContent";
import McpSidebarGroup from "./components/McpSidebarGroup";
import MemoizedSidebarGroup from "./components/sidebarBundles";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
import { SidebarHeaderComponent } from "./components/sidebarHeader";
import SidebarSegmentedNav from "./components/sidebarSegmentedNav";
import { useSearchContext } from "./context/SearchContext";
import { computeSectionVisibility } from "./helpers/compute-section-visibility";
import sensitiveSort from "./helpers/sensitive-sort";
import { useDebouncedSearch } from "./hooks/useDebouncedSearch";
import { useSegmentedSidebarPanel } from "./hooks/useSegmentedSidebarPanel";
import { useSidebarFilters } from "./hooks/useSidebarFilters";
import { useSidebarHotkeys } from "./hooks/useSidebarHotkeys";
import {
  MCP_COMPONENT_CATEGORY,
  type SidebarSearchItem,
  useSidebarSearch,
} from "./hooks/useSidebarSearch";

const CATEGORIES = SIDEBAR_CATEGORIES;
const BUNDLES = SIDEBAR_BUNDLES;

// SearchContext / FlowSearchProvider / useSearchContext moved to
// ./context/SearchContext (LE-1736 W32); re-exported here so existing consumers
// (FlowPage, sidebarSegmentedNav) keep importing from this entry point.
export {
  FlowSearchProvider,
  SearchContext,
  type SearchContextType,
  useSearchContext,
} from "./context/SearchContext";

interface FlowSidebarComponentProps {
  isLoading?: boolean;
  showLegacy?: boolean;
  setShowLegacy?: (value: boolean) => void;
}

export function FlowSidebarComponent({ isLoading }: FlowSidebarComponentProps) {
  const { t } = useTranslation();
  const rawData = useTypesStore((state) => state.data);
  const catalogGovernanceEnabled = useUtilityStore(
    (state) => state.catalogGovernanceEnabled,
  );

  // Filter out knowledge components from files_and_knowledge category when ENABLE_KNOWLEDGE_BASES is OFF
  const data = useMemo(() => {
    if (ENABLE_KNOWLEDGE_BASES) {
      return rawData;
    }

    const knowledgeComponentNames = ["KnowledgeBase"];

    // Create a deep copy to avoid mutating the original
    const filteredData = cloneDeep(rawData);

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
  }, [rawData]);

  const {
    getFilterEdge,
    setFilterEdge,
    filterType,
    getFilterComponent,
    setFilterComponent,
  } = useFlowStore(
    useShallow((state) => ({
      getFilterEdge: state.getFilterEdge,
      setFilterEdge: state.setFilterEdge,
      filterType: state.filterType,
      getFilterComponent: state.getFilterComponent,
      setFilterComponent: state.setFilterComponent,
    })),
  );

  const {
    activeSection,
    setOpen,
    setActiveSection,
    open: sidebarOpen,
  } = useSidebar();
  const addComponent = useAddComponent();

  // Get MCP servers for search functionality (only when new sidebar is enabled)
  const {
    data: mcpServers,
    isLoading: mcpLoading,
    isSuccess: mcpSuccess,
  } = useGetMCPServers({ enabled: ENABLE_NEW_SIDEBAR });

  // Get search state from context
  const context = useSearchContext();
  // Unconditional fallback ref to satisfy Rules of Hooks
  const fallbackSearchInputRef = useRef<HTMLInputElement>(null!);
  const {
    search = "",
    setSearch = () => {},
    searchInputRef = fallbackSearchInputRef,
    isSearchFocused = false,
    handleInputFocus = () => {},
    handleInputBlur = () => {},
    handleInputChange: originalHandleInputChange = () => {},
  } = context;

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      originalHandleInputChange(event);
      // Set active section to search when user first enters text
      if (event.target.value.length > 0 && search.length === 0) {
        setActiveSection("search");
      }
    },
    [originalHandleInputChange, search, setActiveSection],
  );

  const showBetaStorage = getBooleanFromStorage("showBeta", true);
  const showLegacyStorage = getBooleanFromStorage("showLegacy", false);

  // Debounced search value for filtering
  const debouncedSearch = useDebouncedSearch(search);

  // State
  const [openCategories, setOpenCategories] = useState<string[]>([]);
  const [showConfig, setShowConfig] = useState(false);
  const [showBeta, setShowBeta] = useState(showBetaStorage);
  const [showLegacy, setShowLegacy] = useState(showLegacyStorage);

  // Functions to handle state changes with localStorage persistence
  const handleSetShowBeta = useCallback((value: boolean) => {
    setShowBeta(value);
    setLocalStorage("showBeta", value.toString());
  }, []);

  const handleSetShowLegacy = useCallback((value: boolean) => {
    setShowLegacy(value);
    setLocalStorage("showLegacy", value.toString());
  }, []);

  // Create base data that includes MCP category when available
  const baseData = useMemo(() => {
    const mcpComponent = data[MCP_COMPONENT_CATEGORY]?.["MCPTools"];
    const dataWithoutMcpTools = mcpComponent
      ? {
          ...data,
          [MCP_COMPONENT_CATEGORY]: Object.fromEntries(
            Object.entries(data[MCP_COMPONENT_CATEGORY]).filter(
              ([, component]) => component !== mcpComponent,
            ),
          ),
        }
      : data;

    if (mcpSuccess && mcpServers && mcpComponent) {
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

      const mcpCategoryData: Record<string, SidebarSearchItem> = {};
      newMcpSearchData.forEach((mcp) => {
        mcpCategoryData[mcp.display_name] = mcp;
      });

      return {
        ...dataWithoutMcpTools,
        MCP: mcpCategoryData,
      };
    }
    return dataWithoutMcpTools;
  }, [data, mcpSuccess, mcpServers]);

  const [dataFilter, setFilterData] = useState(baseData);

  const customComponent = useMemo(() => {
    return data?.["custom_component"]?.["CustomComponent"] ?? null;
  }, [data]);

  const { searchResults, searchFilteredData, mcpSearchData } = useSidebarSearch(
    {
      baseData,
      debouncedSearch,
      data,
      mcpServers,
      mcpSuccess,
    },
  );

  const sortedCategories = useMemo(() => {
    if (!searchResults || !searchFilteredData) return [];

    return Object.keys(searchFilteredData).toSorted((a, b) =>
      searchResults.fuseCategories.indexOf(b) <
      searchResults.fuseCategories.indexOf(a)
        ? 1
        : -1,
    );
  }, [searchResults, searchFilteredData, CATEGORIES, BUNDLES]);

  const finalFilteredData = useSidebarFilters({
    searchFilteredData,
    getFilterEdge,
    getFilterComponent,
    showBeta,
    showLegacy,
  });

  const hasResults = useMemo(() => {
    return Object.entries(dataFilter).some(
      ([category, items]) =>
        (Object.keys(items).length > 0 &&
          (CATEGORIES.find((c) => c.name === category) ||
            BUNDLES.find((b) => b.name === category))) ||
        (dataFilter["MCP"] && Object.keys(dataFilter["MCP"]).length > 0),
    );
  }, [dataFilter]);

  const isCatalogPolicyEmpty = useMemo(
    () =>
      catalogGovernanceEnabled &&
      Object.values(baseData).every((items) => Object.keys(items).length === 0),
    [baseData, catalogGovernanceEnabled],
  );

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
    if (filterType || getFilterComponent !== "") {
      setOpen(true);
      setActiveSection("search");
    }
  }, [filterType, getFilterComponent, setOpen]);

  useEffect(() => {
    setFilterData(finalFilteredData);

    if (
      debouncedSearch !== "" ||
      filterType ||
      getFilterEdge.length > 0 ||
      getFilterComponent !== ""
    ) {
      const newOpenCategories = Object.keys(finalFilteredData).filter(
        (cat) => Object.keys(finalFilteredData[cat]).length > 0,
      );
      setOpenCategories(newOpenCategories);
    }
  }, [
    finalFilteredData,
    debouncedSearch,
    filterType,
    getFilterEdge,
    setFilterComponent,
    getFilterComponent,
  ]);

  useEffect(() => {
    if (getFilterEdge.length !== 0 || getFilterComponent !== "") {
      setSearch("");
    }
  }, [getFilterEdge, getFilterComponent, baseData]);

  useEffect(() => {
    if (
      debouncedSearch === "" &&
      getFilterEdge.length === 0 &&
      getFilterComponent === ""
    ) {
      setOpenCategories([]);
    }
  }, [debouncedSearch, getFilterEdge, getFilterComponent]);

  const isSearchHotkeyReady = useSidebarHotkeys({
    searchInputRef,
    setOpen,
    isSearchFocused,
  });

  const onDragStart = useCallback(
    (
      event: React.DragEvent<HTMLElement>,
      data: { type: string; node?: APIClassType },
    ) => {
      const crt = event.currentTarget.cloneNode(true) as HTMLElement;
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
    return result;
  }, [dataFilter]);

  const hasBundleItems = useMemo(() => {
    const bundlesWithItems = BUNDLES.filter(
      (item) =>
        dataFilter[item.name] && Object.keys(dataFilter[item.name]).length > 0,
    );
    const result = bundlesWithItems.length > 0;
    return result;
  }, [dataFilter]);

  const hasMcpComponents = useMemo(() => {
    return dataFilter["MCP"] && Object.keys(dataFilter["MCP"]).length > 0;
  }, [dataFilter]);

  const hasMcpServers = Boolean(mcpServers && mcpServers.length > 0);

  const hasSearchInput =
    debouncedSearch !== "" ||
    filterType !== undefined ||
    getFilterComponent !== "";

  const {
    showComponents,
    showBundles,
    showMcp,
    isMcpTabActive,
    showDiscoverMore,
  } = computeSectionVisibility({
    enableNewSidebar: ENABLE_NEW_SIDEBAR,
    activeSection,
    hasSearchInput,
    hasCoreComponents,
    hasMcpComponents,
    hasBundleItems,
  });
  const showVersions =
    ENABLE_NEW_SIDEBAR && activeSection === "versions" && sidebarOpen;

  const currentFlowForVersions = useFlowStore((state) => state.currentFlow);

  const showTraces = ENABLE_NEW_SIDEBAR && activeSection === "traces";
  const showMemories = ENABLE_NEW_SIDEBAR && activeSection === "memories";
  const showAgent = ENABLE_NEW_SIDEBAR && activeSection === "agent";

  const isFeatureSection = showTraces || showMemories || showAgent;
  const previousSidebarOpenRef = useRef(sidebarOpen);
  const isFullSidebarPanelHidden = ENABLE_NEW_SIDEBAR && !sidebarOpen;

  const { isFullSidebarPanelMounted, isFullSidebarPanelShown } =
    useSegmentedSidebarPanel(isFeatureSection);

  useEffect(() => {
    const wasSidebarOpen = previousSidebarOpenRef.current;
    previousSidebarOpenRef.current = sidebarOpen;

    if (!ENABLE_NEW_SIDEBAR || wasSidebarOpen === sidebarOpen) return;

    requestAnimationFrame(() => {
      const navItemSelector = sidebarOpen
        ? "data-sidebar-nav-item"
        : "data-sidebar-collapsed-nav-item";
      const nextFocusTarget =
        document.querySelector<HTMLButtonElement>(
          `[${navItemSelector}="${activeSection}"]`,
        ) ?? document.querySelector<HTMLButtonElement>(`[${navItemSelector}]`);

      nextFocusTarget?.focus();
    });
  }, [activeSection, sidebarOpen]);

  const [category, component] = getFilterComponent?.split(".") ?? ["", ""];

  const filterDescription =
    getFilterComponent !== ""
      ? (baseData[category][component]?.display_name ?? "")
      : (filterType?.type ?? "");

  const filterName =
    getFilterComponent !== ""
      ? "Component"
      : filterType
        ? filterType.source
          ? "Input"
          : "Output"
        : "";

  const resetFilters = useCallback(() => {
    setFilterEdge([]);
    setFilterComponent("");
    setFilterData(baseData);
  }, [setFilterEdge, setFilterComponent, setFilterData, baseData]);

  return (
    <Sidebar
      collapsible="offcanvas"
      data-testid="shad-sidebar"
      data-search-hotkey-ready={isSearchHotkeyReady ? "true" : "false"}
      className="noflow select-none"
      role="navigation"
      aria-label={t("sidebar.componentsPanel")}
    >
      <div className="flex h-full">
        {ENABLE_NEW_SIDEBAR && (
          <SidebarSegmentedNav hiddenFromTabOrder={isFullSidebarPanelHidden} />
        )}
        <div
          inert={isFullSidebarPanelHidden}
          aria-hidden={isFullSidebarPanelHidden}
          className={cn(
            "flex flex-col h-full w-full group-data-[collapsible=icon]:hidden",
            ENABLE_NEW_SIDEBAR && "sidebar-segmented",
            !isFullSidebarPanelMounted && "hidden",
            isFullSidebarPanelMounted &&
              !isFullSidebarPanelShown &&
              "opacity-0 pointer-events-none",
          )}
        >
          {showVersions && currentFlowForVersions?.id ? (
            <FlowVersionSidebarContent flowId={currentFlowForVersions.id} />
          ) : (
            <>
              {isFullSidebarPanelMounted && (
                <SidebarHeaderComponent
                  showConfig={showConfig}
                  setShowConfig={setShowConfig}
                  showBeta={showBeta}
                  setShowBeta={handleSetShowBeta}
                  showLegacy={showLegacy}
                  setShowLegacy={handleSetShowLegacy}
                  searchInputRef={searchInputRef}
                  isInputFocused={isSearchFocused}
                  search={search}
                  handleInputFocus={handleInputFocus}
                  handleInputBlur={handleInputBlur}
                  handleInputChange={handleInputChange}
                  filterName={filterName}
                  filterDescription={filterDescription}
                  resetFilters={resetFilters}
                />
              )}

              <SidebarContent
                segmentedSidebar={ENABLE_NEW_SIDEBAR}
                className="flex-1 group-data-[collapsible=icon]:hidden gutter-stable"
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
                        {showComponents && !isMcpTabActive && (
                          <CategoryGroup
                            dataFilter={dataFilter}
                            sortedCategories={sortedCategories}
                            CATEGORIES={CATEGORIES}
                            openCategories={openCategories}
                            setOpenCategories={setOpenCategories}
                            search={debouncedSearch}
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
                              hasSearchInput
                                ? Object.values(dataFilter["MCP"] || {})
                                : mcpSearchData
                            }
                            nodeColors={nodeColors}
                            onDragStart={onDragStart}
                            openCategories={openCategories}
                            mcpLoading={mcpLoading}
                            mcpSuccess={mcpSuccess}
                            search={debouncedSearch}
                            hasMcpServers={hasMcpServers}
                            showSearchConfigTrigger={
                              activeSection !== "mcp" &&
                              !showComponents &&
                              showBundles
                            }
                            showConfig={showConfig}
                            setShowConfig={setShowConfig}
                          />
                        )}
                        {showBundles && (
                          <MemoizedSidebarGroup
                            BUNDLES={BUNDLES}
                            search={debouncedSearch}
                            sortedCategories={sortedCategories}
                            dataFilter={dataFilter}
                            nodeColors={nodeColors}
                            onDragStart={onDragStart}
                            sensitiveSort={sensitiveSort}
                            openCategories={openCategories}
                            setOpenCategories={setOpenCategories}
                            handleKeyDownInput={handleKeyDownInput}
                            showSearchConfigTrigger={
                              activeSection === "bundles" ||
                              (!showComponents && !showMcp)
                            }
                            showConfig={showConfig}
                            setShowConfig={setShowConfig}
                          />
                        )}
                        {showDiscoverMore && (
                          <Button
                            data-testid="sidebar-discover-more-button"
                            onClick={() => setActiveSection("bundles")}
                            variant="ghost"
                            className="bg-muted hover:bg-muted/70 mx-3 px-2.5 !text-[13px] font-normal line-height-[16px] mb-3 group -mt-3 h-[34px]"
                          >
                            <span className="text-muted-foreground flex items-center">
                              <ForwardedIconComponent
                                name="blocks"
                                className="h-4 w-4"
                              />
                            </span>
                            <ShadTooltip
                              content={t("sidebar.discoverMore")}
                              styleClasses="z-50"
                            >
                              <span className="min-w-0 truncate">
                                {t("sidebar.discoverMore")}
                              </span>
                            </ShadTooltip>
                          </Button>
                        )}
                      </>
                    ) : (
                      <NoResultsMessage
                        onClearSearch={handleClearSearch}
                        message={
                          isCatalogPolicyEmpty && !hasSearchInput
                            ? t("sidebar.catalogPolicyEmpty")
                            : undefined
                        }
                        showClearSearch={
                          !(isCatalogPolicyEmpty && !hasSearchInput)
                        }
                        showConfig={showConfig}
                        setShowConfig={setShowConfig}
                      />
                    )}
                  </>
                )}
              </SidebarContent>
              {!isFullSidebarPanelMounted ||
              (ENABLE_NEW_SIDEBAR &&
                activeSection === "mcp" &&
                !hasMcpServers) ? null : (
                <SidebarFooter className="border-t group-data-[collapsible=icon]:hidden p-1 gap-1 empty:hidden empty:border-0">
                  <SidebarMenuButtons
                    customComponent={customComponent}
                    addComponent={addComponent}
                    isLoading={isLoading}
                  />
                </SidebarFooter>
              )}
            </>
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
