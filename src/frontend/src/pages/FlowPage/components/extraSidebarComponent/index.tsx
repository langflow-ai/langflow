import { ENABLE_MVPS } from "@/customization/feature-flags";
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

import Fuse from "fuse.js";
import { SidebarFilterComponent } from "./sidebarFilterComponent";
import { sortKeys } from "./utils";

export default function ExtraSidebar(): JSX.Element {
  const data = useTypesStore((state) => state.data);
  const templates = useTypesStore((state) => state.templates);
  const getFilterEdge = useFlowStore((state) => state.getFilterEdge);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const hasStore = useStoreStore((state) => state.hasStore);
  const filterType = useFlowStore((state) => state.filterType);

  const arrayData = convertStructureToArray(data);

  function convertStructureToArray(structure) {
    return Object.entries(structure).map(([key, value]) => {
      if (typeof value === "object" && value !== null) {
        return { key, value };
      } else {
        return { key, value: {} };
      }
    });
  }

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [dataFilter, setFilterData] = useState(arrayData);
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

  const fuse = new Fuse(arrayData, { keys: ["key", "value"] });

  // Handle showing components after use search input
  function handleSearchInput(e: string) {
    if (e === "") {
      setFilterData(arrayData);
      return;
    }
    const searchValues = fuse.search(e);

    setFilterData(searchValues.map((item) => item.item));
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
      setFilterData(arrayData);
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
      setFilterData(arrayData);
    }
  }, [getFilterEdge, data]);

  useEffect(() => {
    handleSearchInput(search);
  }, [data]);

  useEffect(() => {
    if (getFilterEdge?.length > 0) {
      setFilterData((_) => {
        let dataClone = cloneDeep(arrayData);
        let ret: { key: string; value: any }[] = [];

        dataClone.forEach((item) => {
          let newItem: { key: string; value: any } = {
            key: item.key,
            value: {},
          };
          if (getFilterEdge.some((x) => x.family === item.key)) {
            newItem.value = item.value;

            const filtered =
              getFilterEdge
                .filter((x) => x.family === item.key)
                .pop()
                ?.type.split(",")
                .map((x) => x.trimStart())
                .filter((x) => x !== "") || [];

            if (filtered.length > 0) {
              let keys = Object.keys(item.value).filter((nd) =>
                filtered.includes(nd),
              );
              newItem.value = Object.fromEntries(
                Object.entries(item.value).filter(([key]) =>
                  keys.includes(key),
                ),
              );
            }
          }
          if (Object.keys(newItem.value).length > 0) {
            ret.push(newItem);
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
              setFilterData(arrayData);
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
                  setFilterData(arrayData);
                }}
              />
            )}
          </div>
        </div>
        <Separator />
        {dataFilter
          .filter((item) => PRIORITY_SIDEBAR_ORDER.includes(item.key))
          .map((item, index) =>
            Object.keys(item.value).length > 0 ? (
              <SidebarCategoryComponent
                key={`DisclosureComponent${index + search + JSON.stringify(getFilterEdge)}`}
                search={search}
                getFilterEdge={getFilterEdge}
                category={item.value}
                name={item.key}
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

              <span className="components-disclosure-title">Discover More</span>
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
          {dataFilter
            .sort((a, b) => sortKeys(a.key, b.key))
            .filter(
              (item) =>
                !PRIORITY_SIDEBAR_ORDER.includes(item.key) &&
                !BUNDLES_SIDEBAR_FOLDER_NAMES.includes(item.key),
            )
            .map((item, index) =>
              Object.keys(item.value).length > 0 ? (
                <SidebarCategoryComponent
                  key={`DisclosureComponent${index + search + JSON.stringify(getFilterEdge)}`}
                  search={search}
                  getFilterEdge={getFilterEdge}
                  category={item.value}
                  name={item.key}
                  onDragStart={onDragStart}
                />
              ) : (
                <div key={index}></div>
              ),
            )}
        </ParentDisclosureComponent>
        {ENABLE_MVPS && (
          <>
            <Separator />

            <ParentDisclosureComponent
              defaultOpen={search.length !== 0 || getFilterEdge.length !== 0}
              key={`${search.length !== 0}-${getFilterEdge.length !== 0}-Bundle`}
              button={{
                title: "Bundles",
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
          </>
        )}
      </div>
    </div>
  );
}
