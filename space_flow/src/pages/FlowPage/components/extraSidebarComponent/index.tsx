import { Bars2Icon, CommandLineIcon, CpuChipIcon, LightBulbIcon, LinkIcon, RocketLaunchIcon, WrenchScrewdriverIcon, ViewColumnsIcon } from "@heroicons/react/24/outline";
import { llm_chain } from "../../../../data_assets/llm_chain";
import { prompt } from "../../../../data_assets/prompt";
import DisclosureComponent from "../DisclosureComponent";

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
      <DisclosureComponent button={{ title: "Prompts", Icon: CommandLineIcon }}>
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "promptNode")}
        >
          <span className="text-black">Prompt</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
      <DisclosureComponent button={{ title: "Models", Icon: LightBulbIcon }}>
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "modelNode")}
        >
          <span className="text-black">Model</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
      <DisclosureComponent button={{ title: "Chains", Icon: LinkIcon }}>
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "chainNode")}
        >
          <span className="text-black">Chain</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
      <DisclosureComponent button={{ title: "Agents", Icon: RocketLaunchIcon }}>
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "agentNode")}
        >
          <span className="text-black">Agent</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
      <DisclosureComponent
        button={{ title: "Tools", Icon: WrenchScrewdriverIcon }}
      >
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "toolNode")}
        >
          <span className="text-black">tools</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
      <DisclosureComponent
        button={{ title: "Memories", Icon: CpuChipIcon }}
      >
        <div
          draggable
          className="flex justify-between text-sm p-4 items-center h-12 m-2 border-dashed border-gray-400 rounded-md border-2 cursor-grab"
          onDragStart={(event) => onDragStart(event, "memoryNode")}
        >
          <span className="text-black">Memory</span>
          <Bars2Icon className="w-6 text-gray-400" />
        </div>
      </DisclosureComponent>
    </div>
  );
}
