import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook"; // Import useHotkeys

import ForwardedIconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
} from "@/components/ui/sidebar";
import { Switch } from "@/components/ui/switch";
import { CustomLink } from "@/customization/components/custom-link";
import { useAddComponent } from "@/hooks/useAddComponent";
import { useStoreStore } from "@/stores/storeStore";
import {
  nodeColors,
  SIDEBAR_BUNDLES,
  SIDEBAR_CATEGORIES,
} from "@/utils/styleUtils";
import { removeCountFromString } from "@/utils/utils";
import { cloneDeep } from "lodash";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { SidebarFilterComponent } from "../extraSidebarComponent/sidebarFilterComponent";
import sensitiveSort from "../extraSidebarComponent/utils/sensitive-sort";
import ShortcutDisplay from "../nodeToolbarComponent/shortcutDisplay";
import SidebarDraggableComponent from "./components/sidebarDraggableComponent";

export function FlowSidebarComponent() {
  const [isInputFocused, setIsInputFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useHotkeys("/", (event) => {
    event.preventDefault();
    searchInputRef.current?.focus();
  });

  // Add this new useHotkeys hook
  useHotkeys(
    "esc",
    (event) => {
      event.preventDefault();
      searchInputRef.current?.blur();
    },
    {
      // Only enable this hotkey when the input is focused
      enableOnFormTags: true,
      enabled: isInputFocused,
    },
  );

  const categories = SIDEBAR_CATEGORIES;
  const bundles = SIDEBAR_BUNDLES;

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

  const hasResults = useMemo(() => {
    return Object.values(dataFilter).some(
      (category) => Object.keys(category).length > 0,
    );
  }, [dataFilter]);

  useEffect(() => {
    filterComponents();
  }, [data, search, filterType, getFilterEdge, showBeta, showLegacy]);
  function normalizeString(str: string): string {
    return str.toLowerCase().replace(/_/g, " ").replace(/\s+/g, "");
  }

  function searchInMetadata(metadata: any, searchTerm: string): boolean {
    if (!metadata || typeof metadata !== "object") return false;

    return Object.entries(metadata).some(([key, value]) => {
      if (typeof value === "string") {
        return (
          normalizeString(key).includes(searchTerm) ||
          normalizeString(value).includes(searchTerm)
        );
      }
      if (typeof value === "object") {
        return searchInMetadata(value, searchTerm);
      }
      return false;
    });
  }

  const filterComponents = () => {
    let filteredData = cloneDeep(data);

    // Apply search filter
    if (search && fuse) {
      const results = fuse.search(search);
      filteredData = Object.fromEntries(
        Object.entries(data).map(([category, items]) => {
          const categoryResults = results.filter(
            (result) => result.item.category === category,
          );
          const filteredItems = Object.fromEntries(
            categoryResults.map((result) => [result.item.key, result.item]),
          );
          return [category, filteredItems];
        }),
      );
    } else {
      // Fallback to traditional search if Fuse.js is not available
      const searchTerm = normalizeString(search);
      filteredData = Object.fromEntries(
        Object.entries(data).map(([category, items]) => {
          const filteredItems = Object.fromEntries(
            Object.entries(items).filter(
              ([key, item]) =>
                normalizeString(key).includes(searchTerm) ||
                normalizeString(item.display_name).includes(searchTerm) ||
                normalizeString(category).includes(searchTerm) ||
                (item.metadata && searchInMetadata(item.metadata, searchTerm)),
            ),
          );
          return [category, filteredItems];
        }),
      );
    }

    // Apply edge filter
    if (getFilterEdge?.length > 0) {
      filteredData = Object.fromEntries(
        Object.entries(filteredData).map(([family, familyData]) => {
          const edgeFilter = getFilterEdge.find((x) => x.family === family);
          if (!edgeFilter) return [family, {}];

          const filteredTypes = edgeFilter.type
            .split(",")
            .map((t) => t.trim())
            .filter((t) => t !== "");

          if (filteredTypes.length === 0) return [family, familyData];

          const filteredFamilyData = Object.fromEntries(
            Object.entries(familyData).filter(([key]) =>
              filteredTypes.includes(key),
            ),
          );

          return [family, filteredFamilyData];
        }),
      );
    }

    // Apply beta filter
    if (!showBeta) {
      filteredData = Object.fromEntries(
        Object.entries(filteredData).map(([category, items]) => [
          category,
          Object.fromEntries(
            Object.entries(items).filter(([_, value]) => !value.beta),
          ),
        ]),
      );
    }

    // Apply legacy filter
    if (!showLegacy) {
      filteredData = Object.fromEntries(
        Object.entries(filteredData).map(([category, items]) => [
          category,
          Object.fromEntries(
            Object.entries(items).filter(([_, value]) => !value.legacy),
          ),
        ]),
      );
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

  useEffect(() => {
    if (search === "" && getFilterEdge.length === 0) {
      setOpenCategories([]);
    }
  }, [search, getFilterEdge]);

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
      keys: ["display_name", "description", "type"],
      threshold: 0.3,
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

  return (
    <Sidebar data-testid="shad-sidebar">
      <SidebarHeader className="flex w-full flex-col gap-4 p-4 pb-1">
        <Disclosure open={showConfig} onOpenChange={setShowConfig}>
          <div className="flex w-full items-center justify-between">
            <h3 className="text-sm font-semibold">Components</h3>
            <DisclosureTrigger>
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
            </DisclosureTrigger>
          </div>
          <DisclosureContent>
            <div className="flex flex-col gap-7 border-b pb-7 pt-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium">
                    Show{" "}
                    <Badge variant="pinkStatic" size="sq">
                      BETA
                    </Badge>{" "}
                    Components
                  </span>
                </div>
                <Switch
                  checked={showBeta}
                  onCheckedChange={setShowBeta}
                  data-testid="sidebar-beta-switch"
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium">
                    Show{" "}
                    <Badge variant="secondaryStatic" size="sq">
                      LEGACY
                    </Badge>{" "}
                    Components
                  </span>
                </div>
                <Switch
                  checked={showLegacy}
                  onCheckedChange={setShowLegacy}
                  data-testid="sidebar-legacy-switch"
                />
              </div>
            </div>
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
            onFocus={() => setIsInputFocused(true)}
            onBlur={() => setIsInputFocused(false)}
            value={search}
            onChange={(e) => handleSearchInput(e.target.value)}
          />
          {!isInputFocused && search === "" && (
            <div className="pointer-events-none absolute inset-y-0 left-8 top-1/2 flex -translate-y-1/2 items-center gap-2 text-sm text-muted-foreground">
              Type{" "}
              <span>
                <ShortcutDisplay sidebar shortcut="/" />
              </span>{" "}
              to search components
            </div>
          )}
        </div>
        {filterType && (
          <SidebarFilterComponent
            isInput={!!filterType.source}
            type={filterType.type}
            resetFilters={() => {
              setFilterEdge([]);
              setFilterData(data);
            }}
          />
        )}
      </SidebarHeader>
      <SidebarContent className="p-2">
        {hasResults ? (
          <>
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  {!data
                    ? Array.from({ length: 5 }).map((_, index) => (
                        <SidebarMenuItem key={index}>
                          <SidebarMenuSkeleton />
                        </SidebarMenuItem>
                      ))
                    : categories.map(
                        (item) =>
                          dataFilter[item.name] &&
                          Object.keys(dataFilter[item.name]).length > 0 && (
                            <Collapsible
                              key={item.name}
                              className="group/collapsible"
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
                                <CollapsibleTrigger asChild>
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
                                        className="h-4 w-4 text-muted-foreground group-data-[state=open]/collapsible:text-pink-600 group-data-[state=open]/collapsible:dark:text-pink-400"
                                      />
                                      <span className="group-data-[state=open]/collapsible:font-semibold">
                                        {item.display_name}
                                      </span>
                                      <ForwardedIconComponent
                                        name="ChevronRight"
                                        className="h-4 w-4 text-muted-foreground transition-all group-data-[state=open]/collapsible:rotate-90"
                                      />
                                    </div>
                                  </SidebarMenuButton>
                                </CollapsibleTrigger>
                                <CollapsibleContent>
                                  <div className="flex flex-col gap-1 py-2">
                                    {Object.keys(dataFilter[item.name])
                                      .sort((a, b) =>
                                        sensitiveSort(
                                          dataFilter[item.name][a].display_name,
                                          dataFilter[item.name][b].display_name,
                                        ),
                                      )
                                      .map((SBItemName: string, idx) => (
                                        <ShadTooltip
                                          content={
                                            dataFilter[item.name][SBItemName]
                                              .display_name
                                          }
                                          side="right"
                                          key={idx}
                                        >
                                          <SidebarDraggableComponent
                                            sectionName={item.name as string}
                                            apiClass={
                                              dataFilter[item.name][SBItemName]
                                            }
                                            icon={
                                              dataFilter[item.name][SBItemName]
                                                .icon ??
                                              item.icon ??
                                              "Unknown"
                                            }
                                            key={idx}
                                            onDragStart={(event) =>
                                              onDragStart(event, {
                                                type: removeCountFromString(
                                                  SBItemName,
                                                ),
                                                node: dataFilter[item.name][
                                                  SBItemName
                                                ],
                                              })
                                            }
                                            color={nodeColors[item.name]}
                                            itemName={SBItemName}
                                            error={
                                              !!dataFilter[item.name][
                                                SBItemName
                                              ].error
                                            }
                                            display_name={
                                              dataFilter[item.name][SBItemName]
                                                .display_name
                                            }
                                            official={
                                              dataFilter[item.name][SBItemName]
                                                .official === false
                                                ? false
                                                : true
                                            }
                                            beta={
                                              dataFilter[item.name][SBItemName]
                                                .beta ?? false
                                            }
                                            legacy={
                                              dataFilter[item.name][SBItemName]
                                                .legacy ?? false
                                            }
                                          />
                                        </ShadTooltip>
                                      ))}
                                  </div>
                                </CollapsibleContent>
                              </SidebarMenuItem>
                            </Collapsible>
                          ),
                      )}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarGroup>
              <SidebarGroupLabel>Bundles</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {!data
                    ? Array.from({ length: 5 }).map((_, index) => (
                        <SidebarMenuItem key={index}>
                          <SidebarMenuSkeleton />
                        </SidebarMenuItem>
                      ))
                    : bundles.map(
                        (item) =>
                          dataFilter[item.name] &&
                          Object.keys(dataFilter[item.name]).length > 0 && (
                            <Collapsible
                              key={item.name}
                              className="group/collapsible"
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
                                <CollapsibleTrigger asChild>
                                  <SidebarMenuButton asChild>
                                    <div
                                      tabIndex={0}
                                      onKeyDown={(e) =>
                                        handleKeyDown(e, item.name)
                                      }
                                      className="flex cursor-pointer items-center gap-2"
                                    >
                                      <ForwardedIconComponent
                                        name={item.icon}
                                        className="h-4 w-4 text-muted-foreground group-data-[state=open]/collapsible:text-pink-600 group-data-[state=open]/collapsible:dark:text-pink-400"
                                      />
                                      <span className="group-data-[state=open]/collapsible:font-semibold">
                                        {item.display_name}
                                      </span>
                                      <ForwardedIconComponent
                                        name="ChevronRight"
                                        className="h-4 w-4 text-muted-foreground transition-all group-data-[state=open]/collapsible:rotate-90"
                                      />
                                    </div>
                                  </SidebarMenuButton>
                                </CollapsibleTrigger>
                                <CollapsibleContent>
                                  <div className="flex flex-col gap-1 py-2">
                                    {Object.keys(dataFilter[item.name])
                                      .sort((a, b) =>
                                        sensitiveSort(
                                          dataFilter[item.name][a].display_name,
                                          dataFilter[item.name][b].display_name,
                                        ),
                                      )
                                      .map((SBItemName: string, idx) => (
                                        <ShadTooltip
                                          content={
                                            dataFilter[item.name][SBItemName]
                                              .display_name
                                          }
                                          side="right"
                                          key={idx}
                                        >
                                          <SidebarDraggableComponent
                                            sectionName={item.name as string}
                                            apiClass={
                                              dataFilter[item.name][SBItemName]
                                            }
                                            icon={
                                              dataFilter[item.name][SBItemName]
                                                .icon ??
                                              item.icon ??
                                              "Unknown"
                                            }
                                            key={idx}
                                            onDragStart={(event) =>
                                              onDragStart(event, {
                                                type: removeCountFromString(
                                                  SBItemName,
                                                ),
                                                node: dataFilter[item.name][
                                                  SBItemName
                                                ],
                                              })
                                            }
                                            color={nodeColors[item.name]}
                                            itemName={SBItemName}
                                            error={
                                              !!dataFilter[item.name][
                                                SBItemName
                                              ].error
                                            }
                                            display_name={
                                              dataFilter[item.name][SBItemName]
                                                .display_name
                                            }
                                            official={
                                              dataFilter[item.name][SBItemName]
                                                .official === false
                                                ? false
                                                : true
                                            }
                                            beta={
                                              dataFilter[item.name][SBItemName]
                                                .beta ?? false
                                            }
                                            legacy={
                                              dataFilter[item.name][SBItemName]
                                                .legacy ?? false
                                            }
                                          />
                                        </ShadTooltip>
                                      ))}
                                  </div>
                                </CollapsibleContent>
                              </SidebarMenuItem>
                            </Collapsible>
                          ),
                      )}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center p-4 text-center">
            <ForwardedIconComponent
              name="Search"
              className="mb-4 h-8 w-8 text-muted-foreground"
            />
            <h3 className="mb-2 text-lg font-semibold">No results found</h3>
            <p className="text-sm text-muted-foreground">
              Try adjusting your search or filter to find what you're looking
              for.
            </p>
          </div>
        )}
      </SidebarContent>
      <SidebarFooter className="border-t p-4 py-3">
        {hasStore && (
          <SidebarMenuButton asChild>
            <CustomLink to="/store">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="Store"
                  className="h-4 w-4 text-muted-foreground"
                />
                <span className="group-data-[state=open]/collapsible:font-semibold">
                  Discover more components
                </span>
              </div>
            </CustomLink>
          </SidebarMenuButton>
        )}
        <SidebarMenuButton asChild>
          <Button
            unstyled
            onClick={() => {
              if (customComponent) {
                addComponent(customComponent, "CustomComponent");
              }
            }}
            data-testid="sidebar-custom-component-button"
            className="flex items-center gap-2"
          >
            <ForwardedIconComponent
              name="Plus"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="group-data-[state=open]/collapsible:font-semibold">
              Custom Component
            </span>
          </Button>
        </SidebarMenuButton>
      </SidebarFooter>
    </Sidebar>
  );
}
