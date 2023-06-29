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
import { INPUT_STYLE } from "../../../../constants";
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
    <div className="w-52 flex flex-col overflow-hidden scrollbar-hide h-full border-r">
      <div className="mt-2 mb-2 w-full flex gap-2 justify-between px-2 items-center">
        <ShadTooltip content="Import" side="top">
          <button
            className="hover:dark:hover:bg-[#242f47] text-gray-700 w-full justify-center shadow-sm transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300  relative inline-flex items-center rounded-md bg-white px-2 py-2 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
            onClick={() => {
              // openPopUp(<ImportModal />);
              uploadFlow();
            }}
          >
            <FileUp className="w-5 h-5 dark:text-gray-300"></FileUp>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Export" side="top">
          <button
            className={classNames(
              "hover:dark:hover:bg-[#242f47] text-gray-700 w-full justify-center shadow-sm transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300  relative inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-gray-50 rounded-md"
            )}
            onClick={(event) => {
              openPopUp(<ExportModal />);
            }}
          >
            <FileDown className="w-5 h-5  dark:text-gray-300"></FileDown>
          </button>
        </ShadTooltip>
        <ShadTooltip content="Code" side="top">
          <button
            className={classNames(
              "hover:dark:hover:bg-[#242f47] text-gray-700 w-full justify-center shadow-sm transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300  relative inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-gray-50 rounded-md"
            )}
            onClick={(event) => {
              openPopUp(<ApiModal flow={flows.find((f) => f.id === tabId)} />);
            }}
          >
            <Code2 className="w-5 h-5  dark:text-gray-300"></Code2>
          </button>
        </ShadTooltip>

        <ShadTooltip content="Save" side="top">
          <button
            className="hover:dark:hover:bg-[#242f47] text-gray-700 w-full justify-center transition-all shadow-sm duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300  relative inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-gray-50 rounded-md"
            onClick={(event) => {
              saveFlow(flows.find((f) => f.id === tabId));
              setSuccessData({ title: "Changes saved successfully" });
            }}
            disabled={!isPending}
          >
            <Save
              className={
                "w-5 h-5" + (isPending ? " " : " text-muted-foreground")
              }
            ></Save>
          </button>
        </ShadTooltip>
      </div>
      <Separator />
      <div className="relative mt-2 flex items-center mb-2 mx-2">
        <input
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className={
            INPUT_STYLE +
            "w-full border-1 dark:border-slate-600 dark:border-0.5 dark:ring-0 focus-visible:dark:ring-0 focus-visible:dark:ring-offset-1 rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
          }
          onChange={(e) => {
            handleSearchInput(e.target.value);
            setSearch(e.target.value);
          }}
        />
        <div className="absolute inset-y-0 right-0 flex py-1.5 pr-3 items-center">
          <Search size={20} color="#000000" />
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
                <div className="p-2 flex flex-col gap-2">
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
                            className={" cursor-grab border-l-8 rounded-l-md"}
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
                            <div className="flex w-full justify-between text-sm px-3 py-1 bg-white dark:bg-gray-800 items-center border-dashed border-gray-400 dark:border-gray-600 border-l-0 rounded-md rounded-l-none border">
                              <span className="text-black dark:text-white w-full pr-1 truncate text-xs">
                                {data[d][t].display_name}
                              </span>
                              <Menu className="w-4 h-6  text-gray-400 dark:text-gray-600" />
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
