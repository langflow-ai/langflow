import { useCallback, useContext, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";
import { locationContext } from "../../contexts/locationContext";
import ExtraSidebar from "./components/extraSidebarComponent";
import Chat from "../../components/chatComponent";
import GenericNode from "../../CustomNodes/GenericNode";
import connection from "./components/connection";
import { getConnectedNodes } from "../../utils";
import ChatInputNode from "../../CustomNodes/ChatInputNode";
import ChatOutputNode from "../../CustomNodes/ChatOutputNode";
import InputNode from "../../CustomNodes/InputNode";
const nodeTypes = {
  genericNode:GenericNode,
  inputNode: InputNode,
  chatInputNode:ChatInputNode,
  chatOutputNode:ChatOutputNode,
};

export default function FlowPage() {
  

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
    (params) => {
      /* console.log(params)
      console.log(reactFlowInstance.getNodes())
      console.log(getConnectedNodes(params,reactFlowInstance.getNodes())) */
      setEdges((eds) => addEdge({...params}, eds))
    },
    [reactFlowInstance]
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
      let newId = getId();
      const newNode = {
        id: newId,
        type: data.name === 'str' ? 'inputNode' : (data.name === 'chatInput' ? 'chatInputNode' : (data.name === 'chatOutput' ? 'chatOutputNode' : 'genericNode')),
        position,
        data: { ...data, instance: reactFlowInstance, onDelete: () => {setNodes(reactFlowInstance.getNodes().filter((n)=>n.id !== newId))} },
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
        connectionLineComponent={connection}
        onDragOver={onDragOver}
        onDrop={onDrop}
        fitView
      >
        <Background />
        <Controls></Controls>
      </ReactFlow>
      <Chat nodes={nodes} edges={edges}/>
    </div>
  );
}
