import { Bars2Icon, ComputerDesktopIcon } from "@heroicons/react/24/outline";
import DisclosureComponent from "../DisclosureComponent";
import {
  nodeColors,
  nodeIcons,
  nodeNames,
  toFirstUpperCase,
} from "../../../../utils";
import { useContext, useEffect, useState } from "react";
import { getAll } from "../../../../controllers/NodesServices";
import { typesContext } from "../../../../contexts/typesContext";

export default function ExtraSidebar() {
  const [data, setData] = useState({});
  const { setTypes} = useContext(typesContext);

  async function getTypes(){
    let d = await getAll();
    setData(d.data);
    setTypes(
      Object.keys(d.data).reduce(
        (acc, curr) => {
          Object.keys(d.data[curr]).forEach((c) => {
            acc[c] = curr;
            d.data[curr][c].base_classes?.forEach((b) => {
              acc[b] = curr;
            });
          });
          return acc;
        },
        {
          str: "advanced",
          bool: "advanced",
          chatOutput: "chat",
          chatInput: "chat",
        }
      )
    );
  }

  useEffect(() => {
    getTypes();
  }, []);


  function onDragStart(event: React.DragEvent<any>, data) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("json", JSON.stringify(data));
  }

  return (
    <div className="mt-4">
      {Object.keys(data).map((d, i) => (
        <DisclosureComponent
          key={i}
          button={{ title: nodeNames[d], Icon: nodeIcons[d] }}
        >
          <div className="p-2 flex flex-col gap-2">
            {Object.keys(data[d]).map((t, k) => (
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
                  <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                    <span className="text-black w-36 truncate">{t}</span>
                    <Bars2Icon className="w-6 h-6 text-gray-400" />
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
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black w-36 truncate">Chat Input</span>
                <Bars2Icon className="w-6 h-6 text-gray-400" />
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
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black w-36 truncate">Chat Output</span>
                <Bars2Icon className="w-6 h-6 text-gray-400" />
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
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black w-36 truncate">String</span>
                <Bars2Icon className="w-6 h-6 text-gray-400" />
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
              <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                <span className="text-black w-36 truncate">Boolean</span>
                <Bars2Icon className="w-6 h-6 text-gray-400" />
              </div>
            </div>
          </div>
        </div>
      </DisclosureComponent>
    </div>
  );
}
