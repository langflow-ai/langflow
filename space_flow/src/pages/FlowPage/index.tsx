import { useCallback, useContext, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useEdgesState,
  useNodesState,
  ReactFlowProvider,
  useReactFlow,
} from "reactflow";
import { locationContext } from "../../contexts/locationContext";
import ExtraSidebar from "./components/extraSidebarComponent";
import Chat from "../../components/chatComponent";
import GenericNode from "../../CustomNodes/GenericNode";
import connection from "./components/connection";
import ChatInputNode from "../../CustomNodes/ChatInputNode";
import ChatOutputNode from "../../CustomNodes/ChatOutputNode";
import InputNode from "../../CustomNodes/InputNode";
import BooleanNode from "../../CustomNodes/BooleanNode";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";

const nodeTypes = {
  genericNode: GenericNode,
  inputNode: InputNode,
  chatInputNode: ChatInputNode,
  chatOutputNode: ChatOutputNode,
  booleanNode: BooleanNode,
};

var _ = require("lodash");

export default function FlowPage({flow}) {
  console.log(flow?.data)

  const {updateFlow} =  useContext(TabsContext)
  const reactFlowWrapper = useRef(null);

  const getId = () => `dndnode_${_.uniqueId()}`;

  const { setExtraComponent, setExtraNavigation } = useContext(locationContext);
  const { setErrorData } = useContext(alertContext);

  const [nodes, setNodes, onNodesChange] = useNodesState(flow?.data?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flow?.data?.edges || []);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const { setViewport } = useReactFlow();

  if(flow?.data && reactFlowInstance){
    setViewport(flow.data.viewport)
  }
  useEffect(()=>{
    if(reactFlowInstance){
      flow.data =reactFlowInstance.toObject() 
      updateFlow(flow)
    }
  },[nodes,edges])

  useEffect(() => {
    setExtraComponent(<ExtraSidebar />);
    setExtraNavigation({ title: "Nodes" });
  }, [setExtraComponent, setExtraNavigation]);

  const onEdgesChangeMod = useCallback(
    (s) => {
      onEdgesChange(s);
      setNodes((x) => {
        let newX = _.cloneDeep(x);
        return newX;
      });
    },
    [onEdgesChange, setNodes]
  );

  const onConnect = useCallback(
    (params) => {
      setEdges((eds) =>
        addEdge({ ...params, className: "animate-pulse" }, eds)
      );
      setNodes((x) => {
        let newX = _.cloneDeep(x);
        return newX;
      });
    },
    [setEdges, setNodes]
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
      if (
        data.type !== "chatInput" ||
        (data.type === "chatInput" &&
          !reactFlowInstance.getNodes().some((n) => n.type === "chatInputNode"))
      ) {
        const position = reactFlowInstance.project({
          x: event.clientX - reactflowBounds.left,
          y: event.clientY - reactflowBounds.top,
        });
        let newId = getId();
        
        const newNode = {
          id: newId,
          type:
            (data.type === "str"
              ? "inputNode"
              : (data.type === "chatInput"
              ? "chatInputNode"
              : (data.type === "chatOutput"
              ? "chatOutputNode"
              : (data.type === "bool"
              ? "booleanNode"
              : "genericNode")))),
          position,
          data: {
            ...data,
            id: newId,
            value: null,
            reactFlowInstance,
            onDelete: () => {
              setNodes(
                reactFlowInstance.getNodes().filter((n) => n.id !== newId)
              );
            },
          },
        };
        setNodes((nds) => nds.concat(newNode));
      } else {
        setErrorData({
          title: "Error creating node",
          list: ["There can't be more than one chat input."],
        });
      }
    },
    [reactFlowInstance, setErrorData, setNodes]
  );

  return (
    <div className="w-full h-full" ref={reactFlowWrapper}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChangeMod}
        onConnect={onConnect}
        onLoad={setReactFlowInstance}
        onInit={setReactFlowInstance}
        nodeTypes={nodeTypes}
        connectionLineComponent={connection}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <Background />
        <Controls ></Controls>
      </ReactFlow>
      <Chat reactFlowInstance={reactFlowInstance} />
    </div>
  );
}
