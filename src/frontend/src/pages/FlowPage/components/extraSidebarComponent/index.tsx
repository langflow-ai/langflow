import { useContext, useEffect, useState } from "react";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { Separator } from "../../../../components/ui/separator";
import { alertContext } from "../../../../contexts/alertContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import { typesContext } from "../../../../contexts/typesContext";
import ApiModal from "../../../../modals/ApiModal";
import ExportModal from "../../../../modals/exportModal";
import { APIClassType, APIObjectType } from "../../../../types/api";
import {
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils/styleUtils";
import { classNames } from "../../../../utils/utils";
import DisclosureComponent from "../DisclosureComponent";

export default function ExtraSidebar() {
  const { data, templates } = useContext(typesContext);
  const { flows, tabId, uploadFlow, tabsState, saveFlow, isBuilt } =
    useContext(TabsContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
  const isPending = tabsState[tabId]?.isPending;
  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType }
  ) {
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
    setFilterData((_) => {
      let ret = {};
      Object.keys(data).forEach((d: keyof APIObjectType, i) => {
        ret[d] = {};
        let keys = Object.keys(data[d]).filter((nd) =>
          nd.toLowerCase().includes(e.toLowerCase())
        );
        keys.forEach((element) => {
          ret[d][element] = data[d][element];
        });
      });
      return ret;
    });
  }
  const flow = flows.find((flow) => flow.id === tabId);
  useEffect(() => {
    // show components with error on load
    let errors = [];
    Object.keys(templates).forEach((component) => {
      if (templates[component].error) {
        errors.push(component);
      }
    });
    if (errors.length > 0)
      setErrorData({ title: " Components with errors: ", list: errors });
  }, []);

  return (
    <div className="side-bar-arrangement">
      <div className="side-bar-buttons-arrangement">
        <div className="side-bar-button">
          <ShadTooltip content="Import" side="top">
            <button
              className="extra-side-bar-buttons"
              onClick={() => {
                uploadFlow();
              }}
            >
              <IconComponent name="FileUp" className="side-bar-button-size " />
            </button>
          </ShadTooltip>
        </div>
        <div className="side-bar-button">
          <ExportModal>
            <ShadTooltip content="Export" side="top">
              <div className={classNames("extra-side-bar-buttons")}>
                <IconComponent
                  name="FileDown"
                  className="side-bar-button-size"
                />
              </div>
            </ShadTooltip>
          </ExportModal>
        </div>
        <ShadTooltip content={"Code"} side="top">
          <div className="side-bar-button">
            {flow && flow.data && (
              <ApiModal flow={flow} disable={!isBuilt}>
                <div className={classNames("extra-side-bar-buttons")}>
                  <IconComponent
                    name="Code2"
                    className={
                      "side-bar-button-size" +
                      (isBuilt ? " " : " extra-side-bar-save-disable")
                    }
                  />
                </div>
              </ApiModal>
            )}
          </div>
        </ShadTooltip>
        <div className="side-bar-button">
          <ShadTooltip content="Save" side="top">
            <button
              className={
                "extra-side-bar-buttons " + (isPending ? "" : "button-disable")
              }
              onClick={(event) => {
                saveFlow(flow);
                setSuccessData({ title: "Changes saved successfully" });
              }}
            >
              <IconComponent
                name="Save"
                className={
                  "side-bar-button-size" +
                  (isPending ? " " : " extra-side-bar-save-disable")
                }
              />
            </button>
          </ShadTooltip>
        </div>
      </div>
      <Separator />
      <div className="side-bar-search-div-placement">
        <Input
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="nopan nodrag noundo nocopy input-search"
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
          .sort()
          .map((SBSectionName: keyof APIObjectType, index) =>
            Object.keys(dataFilter[SBSectionName]).length > 0 ? (
              <DisclosureComponent
                openDisc={search.length == 0 ? false : true}
                key={index}
                button={{
                  title: nodeNames[SBSectionName] ?? nodeNames.unknown,
                  Icon:
                    nodeIconsLucide[SBSectionName] ?? nodeIconsLucide.unknown,
                }}
              >
                <div className="side-bar-components-gap">
                  {Object.keys(dataFilter[SBSectionName])
                    .sort()
                    .map((SBItemName: string, index) => (
                      <ShadTooltip
                        content={data[SBSectionName][SBItemName].display_name}
                        side="right"
                        key={index}
                      >
                        <div key={index} data-tooltip-id={SBItemName}>
                          <div
                            draggable={!data[SBSectionName][SBItemName].error}
                            className={
                              "side-bar-components-border bg-background" +
                              (data[SBSectionName][SBItemName].error
                                ? " cursor-not-allowed select-none"
                                : "")
                            }
                            style={{
                              borderLeftColor:
                                nodeColors[SBSectionName] ?? nodeColors.unknown,
                            }}
                            onDragStart={(event) =>
                              onDragStart(event, {
                                type: SBItemName,
                                node: data[SBSectionName][SBItemName],
                              })
                            }
                            onDragEnd={() => {
                              document.body.removeChild(
                                document.getElementsByClassName(
                                  "cursor-grabbing"
                                )[0]
                              );
                            }}
                          >
                            <div className="side-bar-components-div-form">
                              <span className="side-bar-components-text">
                                {data[SBSectionName][SBItemName].display_name}
                              </span>
                              <IconComponent
                                name="Menu"
                                className="side-bar-components-icon "
                              />
                            </div>
                          </div>
                        </div>
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
