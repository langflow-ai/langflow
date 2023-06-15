import { Bars2Icon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import {
  classNames,
  nodeColors,
  nodeIcons,
  nodeNames,
} from "../../../../utils";
import { useContext, useState } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIObjectType } from "../../../../types/api";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import { Code2, FileDown, FileUp, Save } from "lucide-react";
import { PopUpContext } from "../../../../contexts/popUpContext";
import ImportModal from "../../../../modals/importModal";
import ExportModal from "../../../../modals/exportModal";
import ApiModal from "../../../../modals/ApiModal";
import { TabsContext } from "../../../../contexts/tabsContext";
import { alertContext } from "../../../../contexts/alertContext";
import { updateFlowInDatabase } from "../../../../controllers/API";
import { INPUT_STYLE } from "../../../../constants";
import { Input } from "../../../../components/ui/input";
import { Separator } from "../../../../components/ui/separator";

export default function ExtraSidebar() {
  const { data } = useContext(typesContext);
  const { openPopUp } = useContext(PopUpContext);
  const { flows, tabId, uploadFlow } = useContext(TabsContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");

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

  function handleSaveFlow(flow) {
    try {
      updateFlowInDatabase(flow);
      // updateFlowStyleInDataBase(flow);
    } catch (err) {
      setErrorData(err);
    }
  }

  return (
    <div className="w-56 flex flex-col overflow-hidden scrollbar-hide h-full border-r">
      <div className="mt-2 mb-2 w-full flex gap-2 justify-between px-2 items-center">
        <ShadTooltip delayDuration={1000} content="Import" side="top">
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

        <ShadTooltip delayDuration={1000} content="Export" side="top">
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
        <ShadTooltip delayDuration={1000} content="Code" side="top">
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

        <ShadTooltip delayDuration={1000} content="Save" side="top">
          <button
            className="hover:dark:hover:bg-[#242f47] text-gray-700 w-full justify-center transition-all shadow-sm duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300  relative inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-gray-50 rounded-md"
            onClick={(event) => {
              handleSaveFlow(flows.find((f) => f.id === tabId));
              setSuccessData({ title: "Changes saved successfully" });
            }}
          >
            <Save className="w-5 h-5  dark:text-gray-300"></Save>
          </button>
        </ShadTooltip>
      </div>
      <Separator />
      <div className="relative mt-2 flex items-center mb-2 mx-2">
        <input
          type="text"
          name="search"
          id="search"
          placeholder="Search Nodes"
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
          <MagnifyingGlassIcon className="h-5 w-5 dark:text-white"></MagnifyingGlassIcon>
        </div>
      </div>

      <div className="w-full overflow-auto scrollbar-hide">
        {Object.keys(dataFilter)
          .sort()
          .map((d: keyof APIObjectType, i) =>
            Object.keys(dataFilter[d]).length > 0 ? (
              <DisclosureComponent
                openDisc={search.length == 0 ? false : true}
                key={i}
                button={{
                  title: nodeNames[d] ?? nodeNames.unknown,
                  Icon: nodeIcons[d] ?? nodeIcons.unknown,
                }}
              >
                <div className="p-2 flex flex-col gap-2">
                  {Object.keys(dataFilter[d])
                    .sort()
                    .map((t: string, k) => (
                      <ShadTooltip
                        content={t}
                        delayDuration={1500}
                        side="right"
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
                                {t}
                              </span>
                              <Bars2Icon className="w-4 h-6  text-gray-400 dark:text-gray-600" />
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
