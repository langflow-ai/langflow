import { cloneDeep } from "lodash";
import { useEffect, useMemo, useState } from "react";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { Separator } from "../../../../components/ui/separator";
import ApiModal from "../../../../modals/ApiModal";
import ExportModal from "../../../../modals/exportModal";
import ShareModal from "../../../../modals/shareModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType, APIObjectType } from "../../../../types/api";
import {
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils/styleUtils";
import {
  classNames,
  removeCountFromString,
  sensitiveSort,
} from "../../../../utils/utils";
import DisclosureComponent from "../DisclosureComponent";
import SidebarDraggableComponent from "./sideBarDraggableComponent";

export default function ExtraSidebar(): JSX.Element {
  const data = useTypesStore((state) => state.data);
  const templates = useTypesStore((state) => state.templates);
  const getFilterEdge = useFlowStore((state) => state.getFilterEdge);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);

  const isBuilt = useFlowStore((state) => state.isBuilt);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType }
  ): void {
    //start drag event
    var crt = event.currentTarget.cloneNode(true);
    crt.style.position = "absolute";
    crt.style.top = "-500px";
    crt.style.right = "-500px";
    crt.classList.add("cursor-grabbing");
    document.body.appendChild(crt);
    event.dataTransfer.setDragImage(crt, 0, 0);
    event.dataTransfer.setData("nodedata", JSON.stringify(data));
  }

  // Handle showing components after use search input
  function handleSearchInput(e: string) {
    if (e === "") {
      setFilterData(data);
      return;
    }
    setFilterData((_) => {
      let ret = {};
      Object.keys(data).forEach((d: keyof APIObjectType, i) => {
        ret[d] = {};
        let keys = Object.keys(data[d]).filter(
          (nd) =>
            nd.toLowerCase().includes(e.toLowerCase()) ||
            data[d][nd].display_name?.toLowerCase().includes(e.toLowerCase())
        );
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
                filtered.includes(nd)
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
  }, [getFilterEdge]);

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
                filtered.includes(nd)
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

  const ModalMemo = useMemo(
    () => (
      <ShareModal
        is_component={false}
        component={currentFlow!}
        disabled={!hasApiKey || !validApiKey || !hasStore}
      >
        <button
          disabled={!hasApiKey || !validApiKey || !hasStore}
          className={classNames(
            "extra-side-bar-buttons gap-[4px] text-sm font-semibold",
            !hasApiKey || !validApiKey || !hasStore
              ? "button-disable  cursor-default text-muted-foreground"
              : ""
          )}
        >
          <IconComponent
            name="Share3"
            className={classNames(
              "-m-0.5 -ml-1 h-6 w-6",
              !hasApiKey || !validApiKey || !hasStore
                ? "extra-side-bar-save-disable"
                : ""
            )}
          />
          Share
        </button>
      </ShareModal>
    ),
    [hasApiKey, validApiKey, currentFlow, hasStore]
  );

  const ExportMemo = useMemo(
    () => (
      <ExportModal>
        <button className={classNames("extra-side-bar-buttons")}>
          <IconComponent name="FileDown" className="side-bar-button-size" />
        </button>
      </ExportModal>
    ),
    []
  );

  return (
    <div className="side-bar-arrangement">
      <div className="side-bar-buttons-arrangement">
        {hasStore && validApiKey && (
          <ShadTooltip
            content={
              !hasApiKey || !validApiKey
                ? "Please review your API key."
                : "Share"
            }
            side="top"
            styleClasses="cursor-default"
          >
            <div className="side-bar-button">{ModalMemo}</div>
          </ShadTooltip>
        )}
        <div className="side-bar-button">
          <ShadTooltip content="Import" side="top">
            <button
              className="extra-side-bar-buttons"
              onClick={() => {
                uploadFlow({ newProject: false, isComponent: false }).catch(
                  (error) => {
                    setErrorData({
                      title: "Error uploading file",
                      list: [error],
                    });
                  }
                );
              }}
            >
              <IconComponent name="FileUp" className="side-bar-button-size " />
            </button>
          </ShadTooltip>
        </div>
        {(!hasApiKey || !validApiKey) && (
          <ShadTooltip
            content="Export"
            side="top"
            styleClasses="cursor-default"
          >
            <div className="side-bar-button">{ExportMemo}</div>
          </ShadTooltip>
        )}
        <ShadTooltip content={"Code"} side="top">
          <div className="side-bar-button">
            {currentFlow && currentFlow.data && (
              <ApiModal flow={currentFlow}>
                <button
                  className={"w-full " + (!isBuilt ? "button-disable" : "")}
                >
                  <div className={classNames("extra-side-bar-buttons")}>
                    <IconComponent
                      name="Code2"
                      className={
                        "side-bar-button-size" +
                        (isBuilt ? " " : " extra-side-bar-save-disable")
                      }
                    />
                  </div>
                </button>
              </ApiModal>
            )}
          </div>
        </ShadTooltip>
      </div>
      <Separator />
      <div className="side-bar-search-div-placement">
        <Input
          onFocusCapture={() => handleBlur()}
          value={search}
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="nopan nodelete nodrag noundo nocopy input-search"
          onChange={(event) => {
            handleSearchInput(event.target.value);
            // Set search input state
            setSearch(event.target.value);
          }}
        />
        <div className="search-icon">
          <IconComponent
            name="Search"
            className={"h-5 w-5 stroke-[1.5] text-primary"}
            aria-hidden="true"
          />
        </div>
      </div>

      <div className="side-bar-components-div-arrangement">
        {Object.keys(dataFilter)
          .sort((a, b) => {
            if (a.toLowerCase() === "saved_components") {
              return -1;
            } else if (b.toLowerCase() === "saved_components") {
              return 1;
            } else if (a.toLowerCase() === "custom_components") {
              return -2;
            } else if (b.toLowerCase() === "custom_components") {
              return 2;
            } else {
              return a.localeCompare(b);
            }
          })
          .map((SBSectionName: keyof APIObjectType, index) =>
            Object.keys(dataFilter[SBSectionName]).length > 0 ? (
              <DisclosureComponent
                openDisc={
                  getFilterEdge.length !== 0 || search.length !== 0
                    ? true
                    : false
                }
                key={index + search + JSON.stringify(getFilterEdge)}
                button={{
                  title: nodeNames[SBSectionName] ?? nodeNames.unknown,
                  Icon:
                    nodeIconsLucide[SBSectionName] ?? nodeIconsLucide.unknown,
                }}
              >
                <div className="side-bar-components-gap">
                  {Object.keys(dataFilter[SBSectionName])
                    .sort((a, b) =>
                      sensitiveSort(
                        dataFilter[SBSectionName][a].display_name,
                        dataFilter[SBSectionName][b].display_name
                      )
                    )
                    .map((SBItemName: string, index) => (
                      <ShadTooltip
                        content={
                          dataFilter[SBSectionName][SBItemName].display_name
                        }
                        side="right"
                        key={index}
                      >
                        <SidebarDraggableComponent
                          sectionName={SBSectionName as string}
                          apiClass={dataFilter[SBSectionName][SBItemName]}
                          key={index}
                          onDragStart={(event) =>
                            onDragStart(event, {
                              //split type to remove type in nodes saved with same name removing it's
                              type: removeCountFromString(SBItemName),
                              node: dataFilter[SBSectionName][SBItemName],
                            })
                          }
                          color={nodeColors[SBSectionName]}
                          itemName={SBItemName}
                          //convert error to boolean
                          error={!!dataFilter[SBSectionName][SBItemName].error}
                          display_name={
                            dataFilter[SBSectionName][SBItemName].display_name
                          }
                          official={
                            dataFilter[SBSectionName][SBItemName].official ===
                            false
                              ? false
                              : true
                          }
                        />
                      </ShadTooltip>
                    ))}
                </div>
              </DisclosureComponent>
            ) : (
              <div key={index}></div>
            )
          )}
      </div>
    </div>
  );
}
