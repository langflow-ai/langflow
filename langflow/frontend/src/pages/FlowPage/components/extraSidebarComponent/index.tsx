import { Bars2Icon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import {
  nodeColors,
  nodeIcons,
  nodeNames,
} from "../../../../utils";
import { useContext, useEffect, useState } from "react";
import { getAll } from "../../../../controllers/NodesServices";
import { typesContext } from "../../../../contexts/typesContext";
import { APIClassType, APIKindType, APIObjectType } from "../../../../types/api";

export default function ExtraSidebar() {
  const [data, setData] = useState({});
  const { setTypes} = useContext(typesContext);

  useEffect(() => {
    async function getTypes():Promise<void>{
      const initialValue:{[char: string]: string} = {
        str: "advanced",
        bool: "advanced",
        chatOutput: "chat",
        chatInput: "chat",
      }
      let result = await getAll();
      setData(result.data);
      setTypes(
        Object.keys(result.data).reduce(
          (acc, curr) => {
            Object.keys(result.data[curr]).forEach((c:keyof APIKindType) => {
              acc[c] = curr;
              result.data[curr][c].base_classes?.forEach((b) => {
                acc[b] = curr;
              });
            });
            return acc;
          },
          initialValue
        )
      );
    }
    getTypes();
  }, [setTypes]);


  function onDragStart(event: React.DragEvent<any>, data:{type:string,node?:APIClassType}) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("json", JSON.stringify(data));
  }

  return (
    <div className="mt-4 w-full">
      {Object.keys(data).map((d:keyof APIObjectType, i) => (
        <DisclosureComponent
          key={i}
          button={{ title: nodeNames[d], Icon: nodeIcons[d] }}
        >
          <div className="p-2 flex flex-col gap-2">
            {Object.keys(data[d]).map((t: string, k) => (
              <div key={k}>
                <div
                  draggable
                  className={" cursor-grab border-l-8 rounded-l-md"}
                  style={{ borderLeftColor: nodeColors[d] }}
                  onDragStart={(event) =>
                    onDragStart(event, {
                      type: t,
                      node: data[d][t],
                    })
                  }
                >
                  <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 dark:border-gray-600 border-l-0 rounded-md rounded-l-none border-2">
                    <span className="text-black dark:text-white w-36 truncate">{t}</span>
                    <Bars2Icon className="w-6 h-6 text-gray-400 dark:text-gray-600" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </DisclosureComponent>
      ))}
      <DisclosureComponent
        button={{ title: nodeNames["chat"], Icon: nodeIcons["chat"] }}
      >
        <div className="p-2 flex flex-col gap-2">
          <div>
            <div
              draggable
              className={" cursor-grab border-l-8 rounded-l-md"}
              style={{ borderLeftColor: nodeColors["chat"] }}
              onDragStart={(event) =>
                onDragStart(event, {
                  type: "chatInput",
                })
              }
            >
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 dark:border-gray-600 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black dark:text-white w-36 truncate">Chat Input</span>
                <Bars2Icon className="w-6 h-6 text-gray-400 dark:text-gray-600" />
              </div>
            </div>
          </div>
          <div>
            <div
              draggable
              className={" cursor-grab border-l-8 rounded-l-md"}
              style={{ borderLeftColor: nodeColors["chat"] }}
              onDragStart={(event) =>
                onDragStart(event, {
                  type: "chatOutput",
                })
              }
            >
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center dark:border-gray-600 border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black dark:text-white w-36 truncate">Chat Output</span>
                <Bars2Icon className="w-6 h-6 text-gray-400 dark:text-gray-600" />
              </div>
            </div>
          </div>
        </div>
      </DisclosureComponent>
      <DisclosureComponent
        button={{ title: nodeNames["advanced"], Icon: nodeIcons["advanced"] }}
      >
        <div className="p-2 flex flex-col gap-2">
          <div>
            <div
              draggable
              className={" cursor-grab border-l-8 rounded-l-md"}
              style={{ borderLeftColor: nodeColors["advanced"] }}
              onDragStart={(event) =>
                onDragStart(event, {
                  type: "str",
                })
              }
            >
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed dark:border-gray-600 border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black dark:text-white w-36 truncate">String</span>
                <Bars2Icon className="w-6 h-6 text-gray-400 dark:text-gray-600" />
              </div>
            </div>
          </div>
          <div>
            <div
              draggable
              className={" cursor-grab border-l-8 rounded-l-md"}
              style={{ borderLeftColor: nodeColors["advanced"] }}
              onDragStart={(event) =>
                onDragStart(event, {
                  type: "bool",
                })
              }
            >
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed dark:border-gray-600 border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black dark:text-white w-36 truncate">Boolean</span>
                <Bars2Icon className="w-6 h-6 text-gray-400 dark:text-gray-600" />
              </div>
            </div>
          </div>
        </div>
      </DisclosureComponent>
    </div>
  );
}
