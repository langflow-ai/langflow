import {
  ENABLE_INTEGRATIONS,
  ENABLE_MVPS,
} from "@/customization/feature-flags";
import { useStoreStore } from "@/stores/storeStore";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { Separator } from "../../../../components/ui/separator";
import {
  BUNDLES_SIDEBAR_FOLDER_NAMES,
  PRIORITY_SIDEBAR_ORDER,
} from "../../../../constants/constants";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType, APIObjectType } from "../../../../types/api";
import { nodeIconsLucide } from "../../../../utils/styleUtils";
import ParentDisclosureComponent from "../ParentDisclosureComponent";
import { SidebarCategoryComponent } from "./SidebarCategoryComponent";

import { useUtilityStore } from "@/stores/utilityStore";
import { SidebarFilterComponent } from "./sidebarFilterComponent";
import { sortKeys } from "./utils";

export default function ExtraSidebar(): JSX.Element {
  const data = useTypesStore((state) => state.data);
  const templates = useTypesStore((state) => state.templates);
  const getFilterEdge = useFlowStore((state) => state.getFilterEdge);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const hasStore = useStoreStore((state) => state.hasStore);
  const filterType = useFlowStore((state) => state.filterType);

  const featureFlags = useUtilityStore((state) => state.featureFlags);

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
    <div className="side-bar-arrangement">
      <div className="side-bar-search-div-placement">
        <Input
          onFocusCapture={() => handleBlur()}
          value={search}
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="nopan nodelete nodrag noflow input-search"
          onChange={(event) => {
            handleSearchInput(event.target.value);
            // Set search input state
            setSearch(event.target.value);
          }}
          autoComplete="off"
          readOnly
          onClick={() =>
            document?.getElementById("search")?.removeAttribute("readonly")
          }
        />
        <div
          className="search-icon"
          onClick={() => {
            if (search) {
              setFilterData(data);
              setSearch("");
            }
          }}
        >
          <IconComponent
            name={search ? "X" : "Search"}
            className={`h-5 w-5 stroke-[1.5] text-primary ${
              search ? "cursor-pointer" : "cursor-default"
            }`}
            aria-hidden="true"
          />
        </div>
      </div>
      <Separator />

      <div className="side-bar-components-div-arrangement">
        <div className="parent-disclosure-arrangement">
          <div className="flex w-full flex-col items-start justify-between gap-2.5">
            <span className="text-sm font-medium">Components</span>
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
          </div>
        </div>
        <Separator />
        {Object.keys(dataFilter)
          .sort(sortKeys)
          .filter((x) => PRIORITY_SIDEBAR_ORDER.includes(x))
          .map((SBSectionName: keyof APIObjectType, index) =>
            Object.keys(dataFilter[SBSectionName]).length > 0 ? (
              <SidebarCategoryComponent
                key={`DisclosureComponent${index + search + JSON.stringify(getFilterEdge)}`}
                search={search}
                getFilterEdge={getFilterEdge}
                category={dataFilter[SBSectionName]}
                name={SBSectionName}
                onDragStart={onDragStart}
              />
            ) : (
              <div key={index}></div>
            ),
          )}
        {(ENABLE_INTEGRATIONS || featureFlags?.mvp_components) && (
          <ParentDisclosureComponent
            defaultOpen={true}
            key={`${search.length !== 0}-${getFilterEdge.length !== 0}-Bundle`}
            button={{
              title: "Integrations",
              Icon: nodeIconsLucide.unknown,
            }}
            testId="bundle-extended-disclosure"
          >
            {Object.keys(dataFilter)
              .sort(sortKeys)
              .filter((x) => BUNDLES_SIDEBAR_FOLDER_NAMES.includes(x))
              .map((SBSectionName: keyof APIObjectType, index) =>
                Object.keys(dataFilter[SBSectionName]).length > 0 ? (
                  <SidebarCategoryComponent
                    key={`DisclosureComponent${index + search + JSON.stringify(getFilterEdge)}`}
                    search={search}
                    getFilterEdge={getFilterEdge}
                    category={dataFilter[SBSectionName]}
                    name={SBSectionName}
                    onDragStart={onDragStart}
                  />
                ) : (
                  <div key={index}></div>
                ),
              )}
          </ParentDisclosureComponent>
        )}
        <ParentDisclosureComponent
          defaultOpen={search.length !== 0 || getFilterEdge.length !== 0}
          key={`${search.length !== 0}-${getFilterEdge.length !== 0}-Advanced`}
          button={{
            title: "Experimental",
            Icon: nodeIconsLucide.unknown,
            beta: true,
          }}
          testId="extended-disclosure"
        >
          {Object.keys(dataFilter)
            .sort(sortKeys)
            .filter(
              (x) =>
                !PRIORITY_SIDEBAR_ORDER.includes(x) &&
                !BUNDLES_SIDEBAR_FOLDER_NAMES.includes(x),
            )
            .map((SBSectionName: keyof APIObjectType, index) =>
              Object.keys(dataFilter[SBSectionName]).length > 0 ? (
                <SidebarCategoryComponent
                  key={`DisclosureComponent${index + search + JSON.stringify(getFilterEdge)}`}
                  search={search}
                  getFilterEdge={getFilterEdge}
                  category={dataFilter[SBSectionName]}
                  name={SBSectionName}
                  onDragStart={onDragStart}
                />
              ) : (
                <div key={index}></div>
              ),
            )}
          {hasStore && (
            <a
              target={"_blank"}
              href="https://langflow.store"
              className="components-disclosure-arrangement"
              draggable="false"
            >
              <div className="flex gap-4">
                {/* BUG ON THIS ICON */}
                <IconComponent
                  name="Sparkles"
                  strokeWidth={1.5}
                  className="w-[22px] text-primary"
                />

                <span className="components-disclosure-title">
                  Discover More
                </span>
              </div>
              <div className="components-disclosure-div">
                <div>
                  <IconComponent
                    name="Link"
                    className="h-4 w-4 text-foreground"
                  />
                </div>
              </div>
            </a>
          )}
        </ParentDisclosureComponent>
      </div>
    </div>
  );
}
