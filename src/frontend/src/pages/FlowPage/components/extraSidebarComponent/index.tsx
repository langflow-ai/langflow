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
  
      // Make an asynchronous API call to retrieve all data.
      let result = await getAll();
  
      // Update the state of the component with the retrieved data.
      setData(result.data);
  
      // Set the types by reducing over the keys of the result data and updating the accumulator.
      setTypes(
        Object.keys(result.data).reduce(
          (acc, curr) => {
            Object.keys(result.data[curr]).forEach((c:keyof APIKindType) => {
              acc[c] = curr;
              // Add the base classes to the accumulator as well.
              result.data[curr][c].base_classes?.forEach((b) => {
                acc[b] = curr;
              });
            });
            return acc;
          },{}
        )
      );
    }
    // Call the getTypes function.
    getTypes();
  }, [setTypes]);


  function onDragStart(event: React.DragEvent<any>, data:{type:string,node?:APIClassType}) {
    //start drag event
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("json", JSON.stringify(data));
  }

  return (
    <div className="mt-1 w-full">
      {Object.keys(data).map((d:keyof APIObjectType, i) => (
        <DisclosureComponent
          key={i}
          button={{ title: nodeNames[d]??nodeNames.unknown, Icon: nodeIcons[d]??nodeIcons.unknown }}
        >
          <div className="p-2 flex flex-col gap-2">
            {Object.keys(data[d]).map((t: string, k) => (
              <div key={k}>
                <div
                  draggable
                  className={" cursor-grab border-l-8 rounded-l-md"}
                  style={{ borderLeftColor: nodeColors[d]??nodeColors.unknown }}
                  onDragStart={(event) =>
                    onDragStart(event, {
                      type: t,
                      node: data[d][t],
                    })
                  }
                >
                  <div className="flex w-full justify-between text-sm px-3 py-1 items-center border-dashed border-gray-400 dark:border-gray-600 border-l-0 rounded-md rounded-l-none border">
                    <span className="text-black dark:text-white w-36 truncate text-xs">{t}</span>
                    <Bars2Icon className="w-4 h-6  text-gray-400 dark:text-gray-600" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </DisclosureComponent>
      ))}
    </div>
  );
}
