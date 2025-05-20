import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import SkeletonGroup from "@/components/ui/skeletonGroup";
import { useAddComponent } from "@/hooks/use-add-component";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useStoreStore } from "@/stores/storeStore";
import { checkChatInput, checkWebhookInput } from "@/utils/reactflowUtils";
import {
  nodeColors,
  SIDEBAR_BUNDLES,
  SIDEBAR_CATEGORIES,
} from "@/utils/styleUtils";
import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShallow } from "zustand/react/shallow";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import isWrappedWithClass from "../PageComponent/utils/is-wrapped-with-class";
import { CategoryGroup } from "./components/categoryGroup";
import NoResultsMessage from "./components/emptySearchComponent";
import MemoizedSidebarGroup from "./components/sidebarBundles";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
import { SidebarHeaderComponent } from "./components/sidebarHeader";
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

  // State
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
  const [fuse, setFuse] = useState<Fuse<any> | null>(null);
  const [openCategories, setOpenCategories] = useState<string[]>([]);
  const [showConfig, setShowConfig] = useState(false);
  const [showBeta, setShowBeta] = useState(true);
  const [showLegacy, setShowLegacy] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);

  const searchInputRef = useRef<HTMLInputElement | null>(null);

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

    return {
      fuseResults,
      fuseCategories: fuseResults.map((result) => result.item.category),
      combinedResults: combinedResultsFn(fuseResults, data),
      traditionalResults: traditionalSearchMetadata(data, searchTerm),
    };
  }, [search, fuse, data]);

  const searchFilteredData = useMemo(() => {
    if (!search || !searchResults) return cloneDeep(data);

    return filteredDataFn(
      data,
      searchResults.combinedResults,
      searchResults.traditionalResults,
    );
  }, [data, search, searchResults]);

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
    return Object.entries(dataFilter).some(
      ([category, items]) =>
        Object.keys(items).length > 0 &&
        (CATEGORIES.find((c) => c.name === category) ||
          BUNDLES.find((b) => b.name === category)),
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
    setFilterData(data);
    setOpenCategories([]);
  }, [data]);

  const handleInputFocus = useCallback(() => {
    setIsInputFocused(true);
  }, []);

  const handleInputBlur = useCallback(() => {
    setIsInputFocused(false);
  }, []);

  const handleSearchInput = useCallback((value: string) => {
    setSearch(value);
  }, []);

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      handleSearchInput(event.target.value);
    },
    [handleSearchInput],
  );

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
  }, [data]);

  useEffect(() => {
    if (getFilterEdge.length !== 0) {
      setSearch("");
    }
  }, [getFilterEdge, data]);

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
      enabled: isInputFocused,
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

  const hasBundleItems = useMemo(
    () =>
      BUNDLES.some(
        (item) =>
          dataFilter[item.name] &&
          Object.keys(dataFilter[item.name]).length > 0,
      ),
    [dataFilter],
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
                />

                {hasBundleItems && (
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
      <SidebarFooter className="border-t p-4 py-3">
        <SidebarMenuButtons
          hasStore={hasStore}
          customComponent={customComponent}
          addComponent={addComponent}
          isLoading={isLoading}
        />
      </SidebarFooter>
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
