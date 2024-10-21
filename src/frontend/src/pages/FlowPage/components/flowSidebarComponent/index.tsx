import { useEffect, useState } from "react";

import ForwardedIconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
  SidebarMenuSub,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";
import { useGetCategoriesQuery } from "@/controllers/API/queries/categories/use-get-categories";
import { useStoreStore } from "@/stores/storeStore";
import { nodeColors } from "@/utils/styleUtils";
import { removeCountFromString } from "@/utils/utils";
import { cloneDeep } from "lodash";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType, APIObjectType } from "../../../../types/api";
import sensitiveSort from "../extraSidebarComponent/utils/sensitive-sort";
import ShortcutDisplay from "../nodeToolbarComponent/shortcutDisplay";
import SidebarDraggableComponent from "./components/sidebarDraggableComponent";

export function FlowSidebarComponent() {
  const [isInputFocused, setIsInputFocused] = useState(false);

  const { data: categories, isLoading } = useGetCategoriesQuery();

  const data = useTypesStore((state) => state.data);
  const templates = useTypesStore((state) => state.templates);
  const getFilterEdge = useFlowStore((state) => state.getFilterEdge);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const hasStore = useStoreStore((state) => state.hasStore);
  const filterType = useFlowStore((state) => state.filterType);

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
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

  function handleSearchInput(e: string) {
    if (e === "") {
      setFilterData(data);
      return;
    }

    const searchTerm = normalizeString(e);

    setFilterData((_) => {
      let ret: APIObjectType = {};
      Object.keys(data).forEach((d: keyof APIObjectType) => {
        ret[d] = {};
        let keys = Object.keys(data[d]).filter((nd) => {
          const item = data[d][nd];
          return (
            normalizeString(nd).includes(searchTerm) ||
            normalizeString(item.display_name).includes(searchTerm) ||
            normalizeString(d.toString()).includes(searchTerm) ||
            (item.metadata && searchInMetadata(item.metadata, searchTerm))
          );
        });
        keys.forEach((element) => {
          ret[d][element] = data[d][element];
        });
      });
      return ret;
    });
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

  function handleBlur() {
    // check if search is search to reset fitler on click input
    if ((!search && search === "") || search === "search") {
      setFilterData(data);
      setFilterEdge([]);
      setSearch("");
    }
  }

  useEffect(() => {
    if (getFilterEdge.length !== 0) {
      setSearch("");
    }

    if (getFilterEdge.length === 0 && search === "") {
      setSearch("");
      setFilterData(data);
    }
  }, [getFilterEdge, data]);

  useEffect(() => {
    handleSearchInput(search);
  }, [data]);

  useEffect(() => {
    if (getFilterEdge?.length > 0) {
      setFilterData((_) => {
        let dataClone = cloneDeep(data);
        let ret = {};
        Object.keys(dataClone).forEach((d: keyof APIObjectType, i) => {
          ret[d] = {};
          if (getFilterEdge.some((x) => x.family === d)) {
            ret[d] = dataClone[d];

            const filtered = getFilterEdge
              .filter((x) => x.family === d)
              .pop()
              .type.split(",");

            for (let i = 0; i < filtered.length; i++) {
              filtered[i] = filtered[i].trimStart();
            }

            if (filtered.some((x) => x !== "")) {
              let keys = Object.keys(dataClone[d]).filter((nd) =>
                filtered.includes(nd),
              );
              Object.keys(dataClone[d]).forEach((element) => {
                if (!keys.includes(element)) {
                  delete ret[d][element];
                }
              });
            }
          }
        });
        setSearch("");
        return ret;
      });
    }
  }, [getFilterEdge, data]);

  return (
    <Sidebar>
      <SidebarHeader className="flex w-full flex-col gap-4 p-4 pb-1">
        <div className="flex w-full items-center justify-between">
          <h3 className="font-semibold">Components</h3>
          <Button variant="ghost" size="icon">
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className="h-4 w-4 text-muted-foreground"
            />
          </Button>
        </div>
        <div className="relative w-full flex-1">
          <ForwardedIconComponent
            name="Search"
            className="absolute inset-y-0 left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-primary"
          />
          <Input
            type="search"
            className="w-full rounded-lg bg-background pl-8 text-sm"
            onFocus={() => setIsInputFocused(true)}
            onBlur={() => setIsInputFocused(false)}
          />
          {!isInputFocused && (
            <div className="pointer-events-none absolute inset-y-0 left-8 top-1/2 flex -translate-y-1/2 items-center gap-2 text-sm text-muted-foreground">
              Type{" "}
              <span>
                <ShortcutDisplay shortcut="/" />
              </span>{" "}
              to search components
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent className="p-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {isLoading
                ? Array.from({ length: 5 }).map((_, index) => (
                    <SidebarMenuItem key={index}>
                      <SidebarMenuSkeleton />
                    </SidebarMenuItem>
                  ))
                : categories?.categories.map((item) => (
                    <Collapsible className="group/collapsible">
                      <SidebarMenuItem>
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton asChild>
                            <div className="flex cursor-pointer items-center gap-2">
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
                                    apiClass={dataFilter[item.name][SBItemName]}
                                    icon={
                                      dataFilter[item.name][SBItemName].icon ??
                                      item.icon ??
                                      "Unknown"
                                    }
                                    key={idx}
                                    onDragStart={(event) =>
                                      onDragStart(event, {
                                        //split type to remove type in nodes saved with same name removing it's
                                        type: removeCountFromString(SBItemName),
                                        node: dataFilter[item.name][SBItemName],
                                      })
                                    }
                                    color={nodeColors[item.name]}
                                    itemName={SBItemName}
                                    //convert error to boolean
                                    error={
                                      !!dataFilter[item.name][SBItemName].error
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
                                  />
                                </ShadTooltip>
                              ))}
                          </div>
                        </CollapsibleContent>
                      </SidebarMenuItem>
                    </Collapsible>
                  ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Bundles</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {isLoading
                ? Array.from({ length: 5 }).map((_, index) => (
                    <SidebarMenuItem key={index}>
                      <SidebarMenuSkeleton />
                    </SidebarMenuItem>
                  ))
                : categories?.categories
                    .filter((item, index) => index < 2)
                    .map((item) => (
                      <Collapsible className="group/collapsible">
                        <SidebarMenuItem>
                          <CollapsibleTrigger asChild>
                            <SidebarMenuButton asChild>
                              <div className="flex items-center gap-2">
                                <ForwardedIconComponent
                                  name={item.icon}
                                  className="h-4 w-4 text-muted-foreground group-data-[state=open]/collapsible:text-primary"
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
                            <SidebarMenuSub>
                              <SidebarMenuSubItem />
                            </SidebarMenuSub>
                          </CollapsibleContent>
                        </SidebarMenuItem>
                      </Collapsible>
                    ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t p-4 py-3">
        <SidebarMenuButton asChild>
          <a href="https://langflow.store/" target="_blank" rel="noreferrer">
            <div className="flex items-center gap-2">
              <ForwardedIconComponent
                name="Store"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="group-data-[state=open]/collapsible:font-semibold">
                Discover more components
              </span>
            </div>
          </a>
        </SidebarMenuButton>
        <SidebarMenuButton asChild>
          <Button unstyled className="flex items-center gap-2">
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
