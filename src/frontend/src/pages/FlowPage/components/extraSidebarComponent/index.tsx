import DisclosureComponent from "../DisclosureComponent";
import {
  classNames,
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils";
import { useContext, useState } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIObjectType } from "../../../../types/api";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import { Code2, FileDown, FileUp, Save, Search } from "lucide-react";
import { PopUpContext } from "../../../../contexts/popUpContext";
import ExportModal from "../../../../modals/exportModal";
import ApiModal from "../../../../modals/ApiModal";
import { TabsContext } from "../../../../contexts/tabsContext";
import { alertContext } from "../../../../contexts/alertContext";
import { INPUT_SEARCH, INPUT_STYLE } from "../../../../constants";
import { Separator } from "../../../../components/ui/separator";
import { Menu } from "lucide-react";

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
    event.dataTransfer.setData("json", JSON.stringify(data));
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
    <div className="flex h-full w-52 flex-col overflow-hidden border-r scrollbar-hide">
      <div className="mb-2 mt-2 flex w-full items-center justify-between gap-2 px-2">
        <ShadTooltip content="Import" side="top">
          <button
            className="relative inline-flex w-full items-center justify-center rounded-md bg-background   px-2 py-2 text-foreground shadow-sm ring-1 ring-inset ring-input transition-all duration-500 ease-in-out hover:bg-muted"
            onClick={() => {
              // openPopUp(<ImportModal />);
              uploadFlow();
            }}
          >
            <FileUp strokeWidth={1.5} className="h-5 w-5 "></FileUp>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Export" side="top">
          <button
            className={classNames(
              "relative inline-flex w-full items-center justify-center rounded-md bg-background   px-2 py-2 text-foreground shadow-sm ring-1 ring-inset  ring-input transition-all duration-500 ease-in-out hover:bg-muted"
            )}
            onClick={(event) => {
              openPopUp(<ExportModal />);
            }}
          >
            <FileDown strokeWidth={1.5} className="h-5 w-5  "></FileDown>
          </button>
        </ShadTooltip>
        <ShadTooltip content="Code" side="top">
          <button
            className={classNames(
              "relative inline-flex w-full items-center justify-center rounded-md bg-background   px-2 py-2 text-foreground shadow-sm ring-1 ring-inset  ring-input transition-all duration-500 ease-in-out hover:bg-muted"
            )}
            onClick={(event) => {
              openPopUp(<ApiModal flow={flows.find((f) => f.id === tabId)} />);
            }}
          >
            <Code2 strokeWidth={1.5} className="h-5 w-5  "></Code2>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Save" side="top">
          <button
            className="relative inline-flex w-full items-center justify-center rounded-md bg-background   px-2 py-2 text-foreground shadow-sm ring-1 ring-inset  ring-input transition-all duration-500 ease-in-out hover:bg-muted"
            onClick={(event) => {
              saveFlow(flows.find((f) => f.id === tabId));
              setSuccessData({ title: "Changes saved successfully" });
            }}
            disabled={!isPending}
          >
            <Save
              strokeWidth={1.5}
              className={
                "h-5 w-5" + (isPending ? " " : " text-muted-foreground")
              }
            ></Save>
          </button>
        </ShadTooltip>
      </div>
      <Separator />
      <div className="relative mx-auto mb-2 mt-2 flex items-center">
        <input
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className={INPUT_SEARCH}
          onChange={(e) => {
            handleSearchInput(e.target.value);
            setSearch(e.target.value);
          }}
        />
        <div className="absolute inset-y-0 right-0 flex items-center py-1.5 pr-3">
          {/* ! replace hash color here */}
          <Search size={20} strokeWidth={1.5} className="text-primary" />
        </div>
      </div>

      <div className="w-full overflow-auto scrollbar-hide">
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
                <div className="flex flex-col gap-2 p-2">
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
                            className={"cursor-grab rounded-l-md border-l-8"}
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
                            <div className="flex w-full items-center justify-between rounded-md rounded-l-none border border-l-0 border-dashed border-ring  bg-white px-3 py-1 text-sm">
                              <span className="w-full  truncate pr-1 text-xs text-foreground">
                                {data[d][t].display_name}
                              </span>
                              <Menu className="h-6 w-4  text-ring " />
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
