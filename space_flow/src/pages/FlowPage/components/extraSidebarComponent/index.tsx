import { Bars2Icon, ChartBarIcon } from "@heroicons/react/24/outline";
import { llm_chain } from "../../../../data_assets/llm_chain";
import { prompt } from "../../../../data_assets/prompt";
import DisclosureComponent from "../DisclosureComponent";
import { nodeColors, nodeIcons, toFirstUpperCase } from "../../../../utils";
import { useEffect, useState } from "react";
import { getAll } from "../../../../controllers/NodesServices";

export default function ExtraSidebar() {

  const [data, setData] = useState({});

  useEffect(() => {
    getAll().then((d) => { setData(d.data);});
  }, []);

  function onDragStart(event: React.DragEvent<any>, data) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("json", JSON.stringify(data));
  }

  return (
      <div className="mt-4">
      {Object.keys(data).map((d, i) => (
        <DisclosureComponent
          key={i} button={{ title: toFirstUpperCase(d), Icon: nodeIcons[d] }}
        >
          {Object.keys(data[d]).map((t, k) => (
            <div key={k} className="p-2 pb-0">
              <div
                draggable
                className={" cursor-grab border-l-8 rounded-l-md"}
                style={{ borderLeftColor: nodeColors[d] }}
                onDragStart={(event) => onDragStart(event, {type: d, name:t, node: data[d][t]})}
              >
                <div className="flex w-full justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                  <span className="text-black w-36 truncate">{t}</span>
                  <Bars2Icon className="w-6 h-6 text-gray-400" />
                </div>
              </div>
            </div>
          ))}
        </DisclosureComponent>
      ))}
    </div>
  );
}
