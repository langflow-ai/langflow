import { cloneDeep } from "lodash";
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
import { classNames, deepMerge } from "../../../../utils/utils";
import DisclosureComponent from "../DisclosureComponent";

export default function ExtraSidebar() {
  const { data, templates, filterEdge, setFilterEdge } =
    useContext(typesContext);
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

  function handleBlur() {
    if (filterEdge.length > 0) {
      setFilterData(data);
      setFilterEdge([]);
      setSearch("");
    }
  }

  useEffect(() => {
    if(filterEdge?.length > 0){
      setFilterData((_) => {
        let dataClone = cloneDeep(data);

        let retType = {};
        let retDisplayName = {};

        Object.keys(dataClone).forEach((d: keyof APIObjectType, i) => {
          retType[d] = {};
          retDisplayName[d] = {};

          if(filterEdge.some(x => x.family === d)){
            
            retType[d] = dataClone[d];
            retDisplayName[d] = dataClone[d];

            const filtered = filterEdge.filter(x => x.family === d).pop().type.split(',');
            
            for (let i = 0; i < filtered.length; i++) {
              filtered[i] = filtered[i].trimStart();
            }

            if(filtered.some(x => x !== '')){
              let keys = Object.keys(dataClone[d]).filter((nd => filtered.includes(data[d][nd].template._type)));
              Object.keys(dataClone[d]).forEach((element) => {
                if(!keys.includes(element)){
                  delete retType[d][element];
                }
              })
            }

            if(filtered.some(x => x !== '')){
              let keys = Object.keys(dataClone[d]).filter((nd => filtered.includes(data[d][nd].display_name)));
              Object.keys(dataClone[d]).forEach((element) => {
                if(!keys.includes(element)){
                  delete retType[d][element];
                }
              })
            }
          }
        });
        setSearch('search');
        return deepMerge(retType, retDisplayName);
      });
    }
  }, [filterEdge])  

  // Handle showing components after use search input
  function handleSearchInput(e: string) {
    if(e === ''){
      setFilterData(data);
      return;
    }
    setFilterData((_) => {
      
      let retType = {};
      let retDisplayName = {};

      Object.keys(data).forEach((d: keyof APIObjectType, i) => {
        retType[d] = {};

        Object.keys(data[d]).forEach((t: string, k) => {
          let keys = Object.keys(data[d]).filter((nd) =>
          data[d][nd].template._type.toLowerCase().includes(e.toLowerCase())
        );
        keys.forEach((element) => {
          retType[d][element] = data[d][element];
        });
        })
      });

      Object.keys(data).forEach((d: keyof APIObjectType, i) => {
        retDisplayName[d] = {};

        Object.keys(data[d]).forEach((t: string, k) => {
          let keys = Object.keys(data[d]).filter((nd) =>
          data[d][nd].display_name.toLowerCase().includes(e.toLowerCase())
        );
        keys.forEach((element) => {
          retDisplayName[d][element] = data[d][element];
        });
        })
      });

      return deepMerge(retType, retDisplayName);
    });
  }

  
  const flow = flows.find((f) => f.id === tabId);
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
          onFocusCapture={() => handleBlur()}
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="nopan nodrag noundo nocopy input-search"
          onChange={(e) => {
            handleSearchInput(e.target.value);
            // Set search input state
            setSearch(e.target.value);
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
          .map((d: keyof APIObjectType, i) =>
            Object.keys(dataFilter[d]).length > 0 ? (
              <DisclosureComponent
                openDisc={search.length == 0 ? false : true}
                key={i}
                button={{
                  title: nodeNames[d] ?? nodeNames.unknown,
                  Icon: nodeIconsLucide[d] ?? nodeIconsLucide.unknown,
                }}
              >
                <div className="side-bar-components-gap">
                  {Object.keys(dataFilter[d])
                    .sort()
                    .map((t: string, k) => (
                      <ShadTooltip
                        content={data[d][t].display_name}
                        side="right"
                        key={k}
                      >
                        <div key={k} data-tooltip-id={t}>
                          <div
                            draggable={!data[d][t].error}
                            className={
                              "side-bar-components-border bg-background" +
                              (data[d][t].error
                                ? " cursor-not-allowed select-none"
                                : "")
                            }
                            style={{
                              borderLeftColor:
                                nodeColors[d] ?? nodeColors.unknown,
                            }}
                            onDragStart={(event) =>
                              onDragStart(event, {
                                type: t,
                                node: data[d][t],
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
                                {data[d][t].display_name}
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
              <div key={i}></div>
            )
          )}
      </div>
    </div>
  );
}
