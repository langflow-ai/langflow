import { Bars2Icon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import { nodeColors, nodeIcons, nodeNames } from "../../../../utils";
import { useContext, useEffect, useState } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIObjectType } from "../../../../types/api";

export default function ExtraSidebar() {
  const { data } = useContext(typesContext);

  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType }
  ) {
    //start drag event
    event.dataTransfer.effectAllowed = "move";
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
            <div className="flex flex-col gap-2 p-2">
              {Object.keys(data[d])
                .sort()
                .map((t: string, k) => (
                  <div key={k}>
                    <div
                      draggable
                      className={" cursor-grab rounded-l-md border-l-8"}
                      style={{
                        borderLeftColor: nodeColors[d] ?? nodeColors.unknown,
                      }}
                      onDragStart={(event) =>
                        onDragStart(event, {
                          type: t,
                          node: data[d][t],
                        })
                      }
                    >
                      <div className="flex w-full items-center justify-between rounded-md rounded-l-none border border-l-0 border-dashed border-gray-400 px-3 py-1 text-sm dark:border-gray-600">
                        <span className="w-36 truncate pr-1 text-xs text-black dark:text-white">
                          {t}
                        </span>
                        <Bars2Icon className="h-6 w-4  text-gray-400 dark:text-gray-600" />
                      </div>
                    </div>
                  </div>
                ))}
              {Object.keys(data[d]).length === 0 && (
                <div className="text-center text-gray-400">Coming soon</div>
              )}
            </div>
          </DisclosureComponent>
        ))}
    </div>
  );
}
