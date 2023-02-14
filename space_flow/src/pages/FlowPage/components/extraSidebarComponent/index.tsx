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

  function onDragStart(event: React.DragEvent<any>, nodeType) {
    let json;
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
    if (nodeType === "promptNode") {
      json = JSON.stringify(prompt);
    }
    if (nodeType === "modelNode") {
      json = JSON.stringify(llm_chain);
    }
    if (nodeType === "chainNode") {
      json = JSON.stringify({ content: "" });
    }
    if (nodeType === "agentNode") {
      json = JSON.stringify({ content: "" });
    }
    if (nodeType === "toolNode") {
      json = JSON.stringify({ content: "" });
    }
    if (nodeType === "memoryNode") {
      json = JSON.stringify({ content: "" });
    }
    event.dataTransfer.setData("json", json);
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
                onDragStart={(event) => onDragStart(event, "promptNode")}
              >
                <div className="flex justify-between text-sm px-4 py-3 items-center border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2">
                  <span className="text-black truncate">{t}</span>
                  <Bars2Icon className="ml-3 w-6 h-6 text-gray-400" />
                </div>
              </div>
            </div>
          ))}
        </DisclosureComponent>
      ))}
    </div>
  );
}
