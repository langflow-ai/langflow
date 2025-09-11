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
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import SkeletonGroup from "@/components/ui/skeletonGroup";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useAddComponent } from "@/hooks/use-add-component";
import { useShortcutsStore } from "@/stores/shortcuts";
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
import isWrappedWithClass from "../PageComponent/utils/is-wrapped-with-class";
import { CategoryGroup } from "./components/categoryGroup";
import NoResultsMessage from "./components/emptySearchComponent";
import McpSidebarGroup from "./components/McpSidebarGroup";
import MemoizedSidebarGroup from "./components/sidebarBundles";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
import { SidebarHeaderComponent } from "./components/sidebarHeader";
import SidebarSegmentedNav from "./components/sidebarSegmentedNav";
import { applyBetaFilter } from "./helpers/apply-beta-filter";
import { applyComponentFilter } from "./helpers/apply-component-filter";
import { applyEdgeFilter } from "./helpers/apply-edge-filter";
import { applyLegacyFilter } from "./helpers/apply-legacy-filter";
import { combinedResultsFn } from "./helpers/combined-results";
import { filteredDataFn } from "./helpers/filtered-data";
import { normalizeString } from "./helpers/normalize-string";
import sensitiveSort from "./helpers/sensitive-sort";
import { traditionalSearchMetadata } from "./helpers/traditional-search-metadata";

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

  const { activeSection, setOpen, setActiveSection } = useSidebar();
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
  const fallbackSearchInputRef = useRef<HTMLInputElement | null>(null);
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

  // State
  const [fuse, setFuse] = useState<Fuse<any> | null>(null);
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

    const fuseCategories = fuseResults.map((result) => result.item.category);
    const combinedResults = combinedResultsFn(fuseResults, baseData);
    const traditionalResults = traditionalSearchMetadata(baseData, searchTerm);

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

  const hasResults = useMemo(() => {
    return Object.entries(dataFilter).some(
      ([category, items]) =>
        (Object.keys(items).length > 0 &&
          (CATEGORIES.find((c) => c.name === category) ||
            BUNDLES.find((b) => b.name === category))) ||
        (dataFilter["MCP"] && Object.keys(dataFilter["MCP"]).length > 0),
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
    if (filterType || getFilterComponent !== "") {
      setOpen(true);
      setActiveSection("search");
    }
  }, [filterType, getFilterComponent, setOpen]);

  useEffect(() => {
    setFilterData(finalFilteredData);

    if (
      search !== "" ||
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
    search,
    filterType,
    getFilterEdge,
    setFilterComponent,
    getFilterComponent,
  ]);

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

  useEffect(() => {
    if (getFilterEdge.length !== 0 || getFilterComponent !== "") {
      setSearch("");
    }
  }, [getFilterEdge, getFilterComponent, baseData]);

  useEffect(() => {
    if (
      search === "" &&
      getFilterEdge.length === 0 &&
      getFilterComponent === ""
    ) {
      setOpenCategories([]);
    }
  }, [search, getFilterEdge, getFilterComponent]);

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
    search !== "" || filterType !== undefined || getFilterComponent !== "";

  const showComponents =
    (ENABLE_NEW_SIDEBAR &&
      hasCoreComponents &&
      (activeSection === "components" || activeSection === "search")) ||
    (hasSearchInput && hasCoreComponents && ENABLE_NEW_SIDEBAR) ||
    !ENABLE_NEW_SIDEBAR;
  const showBundles =
    (hasBundleItems && ENABLE_NEW_SIDEBAR && activeSection === "bundles") ||
    (hasSearchInput && hasBundleItems && ENABLE_NEW_SIDEBAR) ||
    !ENABLE_NEW_SIDEBAR;
  const showMcp =
    (ENABLE_NEW_SIDEBAR && activeSection === "mcp") ||
    (hasSearchInput && hasMcpComponents && ENABLE_NEW_SIDEBAR);

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
                          hasSearchInput
                            ? Object.values(dataFilter["MCP"] || {})
                            : mcpSearchData
                        }
                        nodeColors={nodeColors}
                        onDragStart={onDragStart}
                        openCategories={openCategories}
                        mcpLoading={mcpLoading}
                        mcpSuccess={mcpSuccess}
                        search={search}
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
                        search={search}
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
                    {showComponents && (
                      <Button
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
                        Discover more components
                      </Button>
                    )}
                  </>
                ) : (
                  <NoResultsMessage
                    onClearSearch={handleClearSearch}
                    showConfig={showConfig}
                    setShowConfig={setShowConfig}
                  />
                )}
              </>
            )}
          </SidebarContent>
          {ENABLE_NEW_SIDEBAR &&
          activeSection === "mcp" &&
          !hasMcpServers ? null : (
            <SidebarFooter className="border-t group-data-[collapsible=icon]:hidden p-1 gap-1">
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
