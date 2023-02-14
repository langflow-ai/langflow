import { useCallback, useContext, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";
import PromptNode from "../../CustomNodes/PromptNode";
import ModelNode from "../../CustomNodes/ModelNode";
import { locationContext } from "../../contexts/locationContext";
import ExtraSidebar from "./components/extraSidebarComponent";
import AgentNode from "../../CustomNodes/AgentNode";
import ChainNode from "../../CustomNodes/ChainNode";
import ToolsNode from "../../CustomNodes/ToolsNode";
import MemoryNode from "../../CustomNodes/MemoryNode";
import axios from "axios";
import { generateUiNode } from "../../controllers/UiGenerator";
import Chat from "../../components/chatComponent";
import { getAll } from "../../controllers/NodesServices";

const nodeTypes = {
  promptNode: PromptNode,
  modelNode: ModelNode,
  chainNode: ChainNode,
  agentNode: AgentNode,
  toolNode: ToolsNode,
  memoryNode:MemoryNode
};

export default function FlowPage() {
  // getPrompts().then(result=>result.forEach(prompt=>console.log(prompt)))
  // getChains().then(result=>console.log(result))
  // getAgents().then(result=>console.log(result))
  // getMemories().then(result=>console.log(result))
  // getModels().then(result=>result.forEach(model=>console.log(model)))

  // outside component to avoid render trigger

  

  const reactFlowWrapper = useRef(null);

  const rfStyle = {
    backgroundCOlor: "#B8CEFF",
  };

  let id = 0;
  
  const getId = () => `dndnode_${id++}`;

  const { setExtraComponent, setExtraNavigation } = useContext(locationContext);

  useEffect(() => {
    setExtraComponent(<ExtraSidebar />);
    setExtraNavigation({title: "Nodes"})
  }, [setExtraComponent, setExtraNavigation]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    []
  );
  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);
  const onDrop = useCallback(
    (event) => {
      event.preventDefault();

      const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const type = event.dataTransfer.getData("application/reactflow");
      let data = JSON.parse(event.dataTransfer.getData("json"));
      // check if the dropped element is valid
      if (typeof type === "undefined" || !type) {
        return;
      }

      const position = reactFlowInstance.project({
        x: event.clientX - reactflowBounds.left,
        y: event.clientY - reactflowBounds.top,
      });
      const newNode = {
        id: getId(),
        type,
        position,
        data: { ...data, delete: () => console.log("asdsdsadad") },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance]
  );

  return (
    <div className="w-full h-full" ref={reactFlowWrapper}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={setReactFlowInstance}
        nodeTypes={nodeTypes}
        onDragOver={onDragOver}
        onDrop={onDrop}
        fitView
      >
        <Background />
        <Controls></Controls>
      </ReactFlow>
      <Chat />
    </div>
  );
}
