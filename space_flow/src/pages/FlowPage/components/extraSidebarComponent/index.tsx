import { Bars2Icon, CommandLineIcon, CpuChipIcon, LightBulbIcon, LinkIcon, RocketLaunchIcon, WrenchScrewdriverIcon, ViewColumnsIcon } from "@heroicons/react/24/outline";
import { llm_chain } from "../../../../data_assets/llm_chain";
import { prompt } from "../../../../data_assets/prompt";
import DisclosureComponent from "../DisclosureComponent";
import { borderLColors, nodeColors, nodeIcons } from "../../../../utils";

export function ExtraSidebar() {
  
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
      <DisclosureComponent
        button={{ title: "Prompts", Icon: nodeIcons['prompt'] }}
      >
        <div className="p-2">
          <div draggable className={" cursor-grab border-l-8 rounded-l-md"} style={{borderLeftColor: nodeColors['prompt']}} onDragStart={(event) => onDragStart(event, "promptNode")}>
          <div
            
            className="flex justify-between text-sm p-4 items-center h-12 border-dashed border-gray-400 border-l-0 rounded-md rounded-l-none border-2"
            
          >
            <span className="text-black">Prompt</span>
            <Bars2Icon className="w-6 text-gray-400" />
          </div>
          </div>
        </div>
      </DisclosureComponent>
    </div>
  );
}
