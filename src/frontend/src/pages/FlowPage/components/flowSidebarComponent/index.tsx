import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook"; // Import useHotkeys

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { Input } from "@/components/ui/input";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarTrigger,
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
import { SidebarFilterComponent } from "../extraSidebarComponent/sidebarFilterComponent";
import sensitiveSort from "../extraSidebarComponent/utils/sensitive-sort";
import ShortcutDisplay from "../nodeToolbarComponent/shortcutDisplay";
import NoResultsMessage from "./components/emptySearchComponent";
import FeatureToggles from "./components/featureTogglesComponent";
import SidebarMenuButtons from "./components/sidebarFooterButtons";
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
  const [isInputFocused, setIsInputFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const data = useTypesStore((state) => state.data);
  const templates = useTypesStore((state) => state.templates);
  const getFilterEdge = useFlowStore((state) => state.getFilterEdge);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const hasStore = useStoreStore((state) => state.hasStore);
  const filterType = useFlowStore((state) => state.filterType);

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

  function handleSearchInput(e: string) {
    setSearch(e);
    filterComponents();
  }

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

  const customComponent = useMemo(() => {
    return data?.["custom_component"]?.["CustomComponent"] ?? null;
  }, [data]);

  const handleKeyDown = (
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

  const nodes = useFlowStore((state) => state.nodes);
  const chatInputAdded = checkChatInput(nodes);

  return (
    <Sidebar
      collapsible="offcanvas"
      data-testid="shad-sidebar"
      className="noflow"
    >
      <SidebarHeader className="flex w-full flex-col gap-4 p-4 pb-1">
        <Disclosure open={showConfig} onOpenChange={setShowConfig}>
          <div className="flex w-full items-center gap-2">
            <SidebarTrigger className="text-muted-foreground">
              <ForwardedIconComponent name="PanelLeftClose" />
            </SidebarTrigger>
            <h3 className="flex-1 text-sm font-semibold">Components</h3>
            <DisclosureTrigger>
              <div>
                <ShadTooltip content="Component settings" styleClasses="z-50">
                  <Button
                    variant={showConfig ? "ghostActive" : "ghost"}
                    size="iconMd"
                    data-testid="sidebar-options-trigger"
                  >
                    <ForwardedIconComponent
                      name="SlidersHorizontal"
                      className="h-4 w-4"
                    />
                  </Button>
                </ShadTooltip>
              </div>
            </DisclosureTrigger>
          </div>
          <DisclosureContent>
            <FeatureToggles
              showBeta={showBeta}
              setShowBeta={setShowBeta}
              showLegacy={showLegacy}
              setShowLegacy={setShowLegacy}
            />
          </DisclosureContent>
        </Disclosure>
        <div className="relative w-full flex-1">
          <ForwardedIconComponent
            name="Search"
            className="absolute inset-y-0 left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-primary"
          />
          <Input
            ref={searchInputRef}
            type="search"
            data-testid="sidebar-search-input"
            className="w-full rounded-lg bg-background pl-8 text-sm"
            placeholder=""
            onFocus={() => setIsInputFocused(true)}
            onBlur={() => setIsInputFocused(false)}
            value={search}
            onChange={(e) => handleSearchInput(e.target.value)}
          />
          {!isInputFocused && search === "" && (
            <div className="pointer-events-none absolute inset-y-0 left-8 top-1/2 flex w-4/5 -translate-y-1/2 items-center justify-between gap-2 text-sm text-muted-foreground">
              Search{" "}
              <span>
                <ShortcutDisplay sidebar shortcut="/" />
              </span>
            </div>
          )}
        </div>
        {filterType && (
          <SidebarFilterComponent
            isInput={!!filterType.source}
            type={filterType.type}
            color={filterType.color}
            resetFilters={() => {
              setFilterEdge([]);
              setFilterData(data);
            }}
          />
        )}
      </SidebarHeader>
      <SidebarContent>
        {hasResults ? (
          <>
            {hasCategoryItems && (
              <SidebarGroup className="p-3">
                <SidebarGroupContent>
                  <SidebarMenu>
                    {!data
                      ? Array.from({ length: 5 }).map((_, index) => (
                          <SidebarMenuItem key={index}>
                            <SidebarMenuSkeleton />
                          </SidebarMenuItem>
                        ))
                      : CATEGORIES.toSorted(
                          (a, b) =>
                            (search !== ""
                              ? sortedCategories
                              : CATEGORIES
                            ).findIndex((value) => value === a.name) -
                            (search !== ""
                              ? sortedCategories
                              : CATEGORIES
                            ).findIndex((value) => value === b.name),
                        ).map(
                          (item) =>
                            dataFilter[item.name] &&
                            Object.keys(dataFilter[item.name]).length > 0 && (
                              <Disclosure
                                key={item.name}
                                open={openCategories.includes(item.name)}
                                onOpenChange={(isOpen) => {
                                  setOpenCategories((prev) =>
                                    isOpen
                                      ? [...prev, item.name]
                                      : prev.filter((cat) => cat !== item.name),
                                  );
                                }}
                              >
                                <SidebarMenuItem>
                                  <DisclosureTrigger className="group/collapsible">
                                    <SidebarMenuButton asChild>
                                      <div
                                        data-testid={`disclosure-${item.display_name.toLocaleLowerCase()}`}
                                        tabIndex={0}
                                        onKeyDown={(e) =>
                                          handleKeyDown(e, item.name)
                                        }
                                        className="flex cursor-pointer items-center gap-2"
                                      >
                                        <ForwardedIconComponent
                                          name={item.icon}
                                          className="h-4 w-4 group-aria-expanded/collapsible:text-accent-pink-foreground"
                                        />
                                        <span className="flex-1 group-aria-expanded/collapsible:font-semibold">
                                          {item.display_name}
                                        </span>
                                        <ForwardedIconComponent
                                          name="ChevronRight"
                                          className="-mr-1 h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
                                        />
                                      </div>
                                    </SidebarMenuButton>
                                  </DisclosureTrigger>
                                  <DisclosureContent>
                                    <SidebarItemsList
                                      item={item}
                                      dataFilter={dataFilter}
                                      nodeColors={nodeColors}
                                      chatInputAdded={chatInputAdded}
                                      onDragStart={onDragStart}
                                      sensitiveSort={sensitiveSort}
                                    />
                                  </DisclosureContent>
                                </SidebarMenuItem>
                              </Disclosure>
                            ),
                        )}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )}
            {hasBundleItems && (
              <SidebarGroup className="p-3">
                <SidebarGroupLabel>Bundles</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {BUNDLES.toSorted(
                      (a, b) =>
                        (search !== "" ? sortedCategories : BUNDLES).findIndex(
                          (value) => value === a.name,
                        ) -
                        (search !== "" ? sortedCategories : BUNDLES).findIndex(
                          (value) => value === b.name,
                        ),
                    ).map(
                      (item) =>
                        dataFilter[item.name] &&
                        Object.keys(dataFilter[item.name]).length > 0 && (
                          <Disclosure
                            key={item.name}
                            open={openCategories.includes(item.name)}
                            onOpenChange={(isOpen) => {
                              setOpenCategories((prev) =>
                                isOpen
                                  ? [...prev, item.name]
                                  : prev.filter((cat) => cat !== item.name),
                              );
                            }}
                          >
                            <SidebarMenuItem>
                              <DisclosureTrigger className="group/collapsible">
                                <SidebarMenuButton asChild>
                                  <div
                                    tabIndex={0}
                                    onKeyDown={(e) =>
                                      handleKeyDown(e, item.name)
                                    }
                                    className="flex cursor-pointer items-center gap-2"
                                    data-testid={`disclosure-bundles-${item.display_name.toLocaleLowerCase()}`}
                                  >
                                    <ForwardedIconComponent
                                      name={item.icon}
                                      className="h-4 w-4 text-muted-foreground group-aria-expanded/collapsible:text-primary"
                                    />
                                    <span className="flex-1 group-aria-expanded/collapsible:font-semibold">
                                      {item.display_name}
                                    </span>
                                    <ForwardedIconComponent
                                      name="ChevronRight"
                                      className="-mr-1 h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
                                    />
                                  </div>
                                </SidebarMenuButton>
                              </DisclosureTrigger>
                              <DisclosureContent>
                                <SidebarItemsList
                                  item={item}
                                  dataFilter={dataFilter}
                                  nodeColors={nodeColors}
                                  chatInputAdded={chatInputAdded}
                                  onDragStart={onDragStart}
                                  sensitiveSort={sensitiveSort}
                                />
                              </DisclosureContent>
                            </SidebarMenuItem>
                          </Disclosure>
                        ),
                    )}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
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
