import { useCallback, useContext, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";
import { locationContext } from "../../contexts/locationContext";
import ExtraSidebar from "./components/extraSidebarComponent";
import Chat from "../../components/chatComponent";
import GenericNode from "../../CustomNodes/GenericNode";

const nodeTypes = {
  genericNode:GenericNode,
};

export default function FlowPage() {
  // getPrompts().then(result=>result.forEach(prompt=>console.log(prompt)))
  // getChains().then(result=>console.log(result))
  // getAgents().then(result=>console.log(result))
  // getMemories().then(result=>console.log(result))
  // getModels().then(result=>result.forEach(model=>console.log(model)))

  // outside component to avoid render trigger

  

  const reactFlowWrapper = useRef(null);

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
      let data = JSON.parse(event.dataTransfer.getData("json"));
      // check if the dropped element is valid

      const position = reactFlowInstance.project({
        x: event.clientX - reactflowBounds.left,
        y: event.clientY - reactflowBounds.top,
      });
      const newNode = {
        id: getId(),
        type: 'genericNode',
        position,
        data: { ...data, onDelete: () => console.log("asdsdsadad"), onRun: () => {} },
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
