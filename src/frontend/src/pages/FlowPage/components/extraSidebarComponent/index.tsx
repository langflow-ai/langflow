import { Bars2Icon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import { nodeColors, nodeIcons, nodeNames } from "../../../../utils";
import { useContext, useEffect, useState } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIObjectType } from "../../../../types/api";
import Tooltip from "../../../../components/TooltipComponent";

export default function ExtraSidebar() {
  const { data } = useContext(typesContext);

  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType }
  ) {
    //start drag event
    var crt = event.currentTarget.cloneNode(true);
    crt.style.position = "absolute"; crt.style.top = "-500px"; crt.style.right = "-500px";
    crt.classList.add("cursor-grabbing");
    document.body.appendChild(crt);
    event.dataTransfer.setDragImage(crt, 0, 0);
    event.dataTransfer.setData("json", JSON.stringify(data));
  }

  return (
    <div className="mt-1 w-full">
      {Object.keys(data)
        .sort()
        .map((d: keyof APIObjectType, i) => (
          <DisclosureComponent
            key={i}
            button={{
              title: nodeNames[d] ?? nodeNames.unknown,
              Icon: nodeIcons[d] ?? nodeIcons.unknown,
            }}
          >
            <div className="p-2 flex flex-col gap-2">
              {Object.keys(data[d])
                .sort()
                .map((t: string, k) => (
                  <Tooltip title={t.length > 21 ? t : ""} placement="right">
                    <div key={k}>
                      <div
                        draggable
                        className={" cursor-grab border-l-8 rounded-l-md"}
                        style={{
                          borderLeftColor: nodeColors[d] ?? nodeColors.unknown,
                        }}
                        onDragStart={(event) =>
                          onDragStart(event, {
                            type: t,
                            node: data[d][t],
                          })
                        }
                        onDragEnd={() => {
                          document.body.removeChild(
                            document.getElementsByClassName("cursor-grabbing")[0]
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
                  </Tooltip>
                ))}
              {Object.keys(data[d]).length === 0 && (
                <div className="text-gray-400 text-center">Coming soon</div>
              )}
            </div>
          </DisclosureComponent>
        ))}
    </div>
  );
}
