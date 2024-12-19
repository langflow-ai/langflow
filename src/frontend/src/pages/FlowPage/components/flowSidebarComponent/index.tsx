import Fuse from "fuse.js";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook"; // Import useHotkeys

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAddComponent } from "@/hooks/useAddComponent";
import { useStoreStore } from "@/stores/storeStore";
import { checkChatInput } from "@/utils/reactflowUtils";
import {
  nodeColors,
  SIDEBAR_BUNDLES,
  SIDEBAR_CATEGORIES,
} from "@/utils/styleUtils";
import { cloneDeep } from "lodash";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import sensitiveSort from "../extraSidebarComponent/utils/sensitive-sort";
import { CategoryGroup } from "./components/categoryGroup";
import NoResultsMessage from "./components/emptySearchComponent";
import MemoizedSidebarGroup from "./components/sidebarBundles";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
import { SidebarHeaderComponent } from "./components/sidebarHeader";
import SidebarItemsList from "./components/sidebarItemsList";
import { applyBetaFilter } from "./helpers/apply-beta-filter";
import { applyEdgeFilter } from "./helpers/apply-edge-filter";
import { applyLegacyFilter } from "./helpers/apply-legacy-filter";
import { combinedResultsFn } from "./helpers/combined-results";
import { filteredDataFn } from "./helpers/filtered-data";
import { normalizeString } from "./helpers/normalize-string";
import { traditionalSearchMetadata } from "./helpers/traditional-search-metadata";

const CATEGORIES = SIDEBAR_CATEGORIES;
const BUNDLES = SIDEBAR_BUNDLES;

export function FlowSidebarComponent() {
  const { data, templates } = useTypesStore(
    useCallback(
      (state) => ({
        data: state.data,
        templates: state.templates,
      }),
      [],
    ),
  );

  const { getFilterEdge, setFilterEdge, filterType, nodes } = useFlowStore(
    useCallback(
      (state) => ({
        getFilterEdge: state.getFilterEdge,
        setFilterEdge: state.setFilterEdge,
        filterType: state.filterType,
        nodes: state.nodes,
      }),
      [],
    ),
  );

  const hasStore = useStoreStore((state) => state.hasStore);

  // Memoized values
  const chatInputAdded = useMemo(() => checkChatInput(nodes), [nodes]);

  const customComponent = useMemo(() => {
    return data?.["custom_component"]?.["CustomComponent"] ?? null;
  }, [data]);

  const getFilteredData = useCallback(
    (searchTerm: string, sourceData: any, fuseInstance: Fuse<any> | null) => {
      if (!searchTerm) return sourceData;

      let filteredData = cloneDeep(sourceData);
      // ... rest of your filtering logic
      return filteredData;
    },
    [],
  );

  // Effect optimizations
  useEffect(() => {
    if (filterType) {
      setOpen(true);
    }
  }, [filterType]);

  useEffect(() => {
    const fuseOptions = {
      keys: ["display_name", "description", "type", "category"],
      threshold: 0.2,
      includeScore: true,
    };

    const fuseData = Object.entries(data).flatMap(([category, items]) =>
      Object.entries(items).map(([key, value]) => ({
        ...value,
        category,
        key,
      })),
    );

    setFuse(new Fuse(fuseData, fuseOptions));
  }, [data]);

  // Event handlers
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (event.key === "/") {
      event.preventDefault();
      searchInputRef.current?.focus();
      setOpen(true);
    }
  }, []);

  const handleKeyDownInput = (
    e: React.KeyboardEvent<HTMLDivElement>,
    name: string,
  ) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpenCategories((prev) =>
        prev.includes(name)
          ? prev.filter((cat) => cat !== name)
          : [...prev, name],
      );
    }
  };

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const [isInputFocused, setIsInputFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
  const addComponent = useAddComponent();

  const [fuse, setFuse] = useState<Fuse<any> | null>(null);

  const [openCategories, setOpenCategories] = useState<string[]>([]);

  const [showConfig, setShowConfig] = useState(false);
  const [showBeta, setShowBeta] = useState(true);
  const [showLegacy, setShowLegacy] = useState(false);

  const { setOpen } = useSidebar();

  useHotkeys("/", (event) => {
    event.preventDefault();
    searchInputRef.current?.focus();

    setOpen(true);
  });

  useHotkeys(
    "esc",
    (event) => {
      event.preventDefault();
      searchInputRef.current?.blur();
    },
    {
      enableOnFormTags: true,
      enabled: isInputFocused,
    },
  );

  useEffect(() => {
    if (filterType) {
      setOpen(true);
    }
  }, [filterType]);

  useEffect(() => {
    filterComponents();
  }, [data, search, filterType, getFilterEdge, showBeta, showLegacy]);

  useEffect(() => {
    // show components with error on load
    let errors: string[] = [];
    Object.keys(templates).forEach((component) => {
      if (templates[component].error) {
        errors.push(component);
      }
    });
    if (errors.length > 0)
      setErrorData({ title: " Components with errors: ", list: errors });
  }, []);

  useEffect(() => {
    if (getFilterEdge.length !== 0) {
      setSearch("");
    }
  }, [getFilterEdge, data]);

  useEffect(() => {
    const options = {
      keys: ["display_name", "description", "type", "category"],
      threshold: 0.2,
      includeScore: true,
    };

    const fuseData = Object.entries(data).flatMap(([category, items]) =>
      Object.entries(items).map(([key, value]) => ({
        ...value,
        category,
        key,
      })),
    );

    setFuse(new Fuse(fuseData, options));
    handleSearchInput(search);
  }, [data]);

  useEffect(() => {
    if (search === "" && getFilterEdge.length === 0) {
      setOpenCategories([]);
    }
  }, [search, getFilterEdge]);

  const hasResults = useMemo(() => {
    return Object.entries(dataFilter).some(
      ([category, items]) =>
        Object.keys(items).length > 0 &&
        (CATEGORIES.find((c) => c.name === category) ||
          BUNDLES.find((b) => b.name === category)),
    );
  }, [dataFilter]);
  const [sortedCategories, setSortedCategories] = useState<string[]>([]);

  const filterComponents = () => {
    let filteredData = cloneDeep(data);

    if (search) {
      const searchTerm = normalizeString(search);
      let combinedResults = {};

      if (fuse) {
        const fuseResults = fuse.search(search).map((result) => ({
          ...result,
          item: { ...result.item, score: result.score },
        }));
        const fuseCategories = fuseResults.map(
          (result) => result.item.category,
        );
        setSortedCategories(fuseCategories);
        combinedResults = combinedResultsFn(fuseResults, data);

        const traditionalResults = traditionalSearchMetadata(data, searchTerm);

        filteredData = filteredDataFn(
          data,
          combinedResults,
          traditionalResults,
        );

        setSortedCategories(
          Object.keys(filteredData)
            .filter(
              (category) =>
                Object.keys(filteredData[category]).length > 0 &&
                (CATEGORIES.find((c) => c.name === category) ||
                  BUNDLES.find((b) => b.name === category)),
            )
            .toSorted((a, b) =>
              fuseCategories.indexOf(b) < fuseCategories.indexOf(a) ? 1 : -1,
            ),
        );
      }
    }

    // Apply edge filter
    if (getFilterEdge?.length > 0) {
      filteredData = applyEdgeFilter(filteredData, getFilterEdge);
    }

    // Apply beta filter
    if (!showBeta) {
      filteredData = applyBetaFilter(filteredData);
    }

    // Apply legacy filter
    if (!showLegacy) {
      filteredData = applyLegacyFilter(filteredData);
    }

    setFilterData(filteredData);
    if (search !== "" || filterType || getFilterEdge.length > 0) {
      setOpenCategories(
        Object.keys(filteredData).filter(
          (cat) => Object.keys(filteredData[cat]).length > 0,
        ),
      );
    }
  };

  const handleSearchInput = useCallback(
    (value: string) => {
      setSearch(value);
      const filtered = getFilteredData(value, data, fuse);
      setFilterData(filtered);
    },
    [data, fuse],
  );

  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ): void {
    //start drag event
    var crt = event.currentTarget.cloneNode(true);
    crt.style.position = "absolute";
    crt.style.width = "215px";
    crt.style.top = "-500px";
    crt.style.right = "-500px";
    crt.classList.add("cursor-grabbing");
    document.body.appendChild(crt);
    event.dataTransfer.setDragImage(crt, 0, 0);
    event.dataTransfer.setData("genericNode", JSON.stringify(data));
  }

  const hasBundleItems = BUNDLES.some(
    (item) =>
      dataFilter[item.name] && Object.keys(dataFilter[item.name]).length > 0,
  );

  const hasCategoryItems = CATEGORIES.some(
    (item) =>
      dataFilter[item.name] && Object.keys(dataFilter[item.name]).length > 0,
  );

  function handleClearSearch() {
    setSearch("");
    setFilterData(data);
    setOpenCategories([]);
  }

  const handleInputFocus = useCallback(
    (event: React.FocusEvent<HTMLInputElement>) => {
      setIsInputFocused(true);
    },
    [],
  );

  const handleInputBlur = useCallback(
    (event: React.FocusEvent<HTMLInputElement>) => {
      setIsInputFocused(false);
    },
    [],
  );

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      handleSearchInput(event.target.value);
    },
    [],
  );

  return (
    <Sidebar
      collapsible="offcanvas"
      data-testid="shad-sidebar"
      className="noflow"
    >
      <SidebarHeaderComponent
        showConfig={showConfig}
        setShowConfig={setShowConfig}
        showBeta={showBeta}
        setShowBeta={setShowBeta}
        showLegacy={showLegacy}
        setShowLegacy={setShowLegacy}
        searchInputRef={searchInputRef}
        isInputFocused={isInputFocused}
        search={search}
        handleInputFocus={handleInputFocus}
        handleInputBlur={handleInputBlur}
        handleInputChange={handleInputChange}
        filterType={filterType}
        setFilterEdge={setFilterEdge}
        setFilterData={setFilterData}
        data={data}
      />
      <SidebarContent>
        {hasResults ? (
          <>
            {hasCategoryItems && (
              <CategoryGroup
                dataFilter={dataFilter}
                sortedCategories={sortedCategories}
                CATEGORIES={CATEGORIES}
                openCategories={openCategories}
                setOpenCategories={setOpenCategories}
                search={search}
                nodeColors={nodeColors}
                chatInputAdded={chatInputAdded}
                onDragStart={onDragStart}
                sensitiveSort={sensitiveSort}
              />
            )}
            {hasBundleItems && (
              <MemoizedSidebarGroup
                BUNDLES={BUNDLES}
                search={search}
                sortedCategories={sortedCategories}
                dataFilter={dataFilter}
                nodeColors={nodeColors}
                chatInputAdded={chatInputAdded}
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
      </SidebarContent>
      <SidebarFooter className="border-t p-4 py-3">
        <SidebarMenuButtons
          hasStore={hasStore}
          customComponent={customComponent}
          addComponent={addComponent}
        />
      </SidebarFooter>
    </Sidebar>
  );
}

FlowSidebarComponent.displayName = "FlowSidebarComponent";

export default memo(FlowSidebarComponent);
