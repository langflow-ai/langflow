import { Bars2Icon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import {
  classNames,
  nodeColors,
  nodeIcons,
  nodeNames,
} from "../../../../utils";
import { useContext, useEffect, useState, useRef } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIObjectType } from "../../../../types/api";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import { INPUT_STYLE } from "../../../../constants";

export default function ExtraSidebar() {
  const { data } = useContext(typesContext);
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

  return (
    <>
      <div className="relative mt-2 flex items-center mb-2 mx-auto">
        <input
          type="text"
          name="search"
          id="search"
          placeholder="Search nodes"
          className={
            INPUT_STYLE +
            "border-1 dark:border-slate-600 dark:border-0.5 dark:ring-0 focus-visible:dark:ring-0 focus-visible:dark:ring-offset-1 rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
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

      <div className="mt-1 w-full">
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
                              <span className="text-black dark:text-white w-36 pr-1 truncate text-xs">
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
    </>
  );
}
