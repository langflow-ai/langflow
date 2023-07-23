import { Code2, FileDown, FileUp, Menu, Save, Search } from "lucide-react";
import { useContext, useState } from "react";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import { Separator } from "../../../../components/ui/separator";
import { alertContext } from "../../../../contexts/alertContext";
import { PopUpContext } from "../../../../contexts/popUpContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import { typesContext } from "../../../../contexts/typesContext";
import ApiModal from "../../../../modals/ApiModal";
import ExportModal from "../../../../modals/exportModal";
import { APIClassType, APIObjectType } from "../../../../types/api";
import {
  classNames,
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils";
import DisclosureComponent from "../DisclosureComponent";

export default function ExtraSidebar() {
  const { data } = useContext(typesContext);
  const { openPopUp } = useContext(PopUpContext);
  const { flows, tabId, uploadFlow, tabsState, saveFlow } =
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

  return (
    <div className="side-bar-arrangement">
      <div className="side-bar-buttons-arrangement">
        <ShadTooltip content="Import" side="top">
          <button
            className="extra-side-bar-buttons"
            onClick={() => {
              // openPopUp(<ImportModal />);
              uploadFlow();
            }}
          >
            <FileUp
              strokeWidth={1.5}
              className="side-bar-button-size "
            ></FileUp>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Export" side="top">
          <button
            className={classNames("extra-side-bar-buttons")}
            onClick={(event) => {
              openPopUp(<ExportModal />);
            }}
          >
            <FileDown
              strokeWidth={1.5}
              className="side-bar-button-size"
            ></FileDown>
          </button>
        </ShadTooltip>
        <ShadTooltip content="Code" side="top">
          <button
            className={classNames("extra-side-bar-buttons")}
            onClick={(event) => {
              openPopUp(<ApiModal flow={flows.find((f) => f.id === tabId)} />);
            }}
          >
            <Code2 strokeWidth={1.5} className="side-bar-button-size"></Code2>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Save" side="top">
          <button
            className="extra-side-bar-buttons"
            onClick={(event) => {
              saveFlow(flows.find((f) => f.id === tabId));
              setSuccessData({ title: "Changes saved successfully" });
            }}
            disabled={!isPending}
          >
            <Save
              strokeWidth={1.5}
              className={
                "side-bar-button-size" +
                (isPending ? " " : " extra-side-bar-save-disable")
              }
            ></Save>
          </button>
        </ShadTooltip>
      </div>
      <Separator />
      <div className="side-bar-search-div-placement">
        <input
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="input-search"
          onChange={(e) => {
            handleSearchInput(e.target.value);
            setSearch(e.target.value);
          }}
        />
        <div className="search-icon">
          {/* ! replace hash color here */}
          <Search size={20} strokeWidth={1.5} className="text-primary" />
        </div>
      </div>

      <div className="side-bar-components-div-arrangement">
        {Object.keys(dataFilter)
          .sort()
          .map((d: keyof APIObjectType, i) =>
            Object.keys(dataFilter[d]).length > 0 ? (
              <DisclosureComponent
                openDisc={search.length == 0 ? false : true}
                key={nodeNames[d]}
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
                        key={data[d][t].display_name}
                      >
                        <div key={k} data-tooltip-id={t}>
                          <div
                            draggable
                            className={
                              "side-bar-components-border bg-background"
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
                              <Menu className="side-bar-components-icon " />
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
