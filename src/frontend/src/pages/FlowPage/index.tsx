import { useCallback, useContext, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  updateEdge,
  EdgeChange,
  Connection,
  Edge,
  useKeyPress,
  useOnSelectionChange,
} from "reactflow";
import { locationContext } from "../../contexts/locationContext";
import ExtraSidebar from "./components/extraSidebarComponent";
import Chat from "../../components/chatComponent";
import GenericNode from "../../CustomNodes/GenericNode";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import ConnectionLineComponent from "./components/ConnectionLineComponent";
import { FlowType, NodeType } from "../../types/flow";
import { APIClassType } from "../../types/api";
import { isValidConnection } from "../../utils";

const nodeTypes = {
  genericNode: GenericNode,
};

var _ = require("lodash");

export default function FlowPage({ flow }:{flow:FlowType}) {
	let { updateFlow, incrementNodeId} =
		useContext(TabsContext);
	const { types, reactFlowInstance, setReactFlowInstance, templates } =
		useContext(typesContext);
	const reactFlowWrapper = useRef(null);

  const copied = useKeyPress(['Meta+c', 'Strg+c'])
  const pasted = useKeyPress(['Meta+v', 'Strg+v'])
  const [lastSelection, setLastSelection] = useState(null);
  const [lastCopiedSelection, setLastCopiedSelection] = useState(null);

  useOnSelectionChange({
    onChange: (flow) => {setLastSelection(flow);},
  })

  useEffect(() => {
    if(copied === true && lastSelection){
      setLastCopiedSelection(lastSelection);
    }
  }, [copied])

  useEffect(() => {
    if(pasted === true && lastCopiedSelection){
      let maximumHeight = 0;
      let minimumHeight = Infinity;
      let idsMap = {};
      lastCopiedSelection.nodes.forEach((n) => {
        if(n.height + n.position.y > maximumHeight){
          maximumHeight = n.height + n.position.y;
        }
        if(n.position.y < minimumHeight){
          minimumHeight = n.position.y;
        }
      });
      let heightDifference = maximumHeight - minimumHeight + 30;

      lastCopiedSelection.nodes.forEach((n) => {

        // Generate a unique node ID
        let newId = getId();
        idsMap[n.id] = newId;

        // Create a new node object
        const newNode: NodeType = {
          id: newId,
          type: "genericNode",
          position: {
            x: n.position.x,
            y: n.position.y + heightDifference,
          },
          data: {
            ...n.data,
            id: newId,
          },
        };

        // Add the new node to the list of nodes in state
        setNodes((nds) => nds.map((e) => ({...e, selected: false})).concat({...newNode, selected: false}));
      })

      lastCopiedSelection.edges.forEach((e) => {
        let source = idsMap[e.source];
        let target = idsMap[e.target];
        let sourceHandleSplitted = e.sourceHandle.split('|');
        let sourceHandle = sourceHandleSplitted[0] + '|' + source + '|' + sourceHandleSplitted.slice(2).join('|');
        let targetHandleSplitted = e.targetHandle.split('|');
        let targetHandle = targetHandleSplitted.slice(0, -1).join('|') + '|' + target;
        let id = "reactflow__edge-" + source + sourceHandle + "-" + target + targetHandle;
        setEdges((eds) =>
          addEdge({ source, target, sourceHandle, targetHandle, id, className: "animate-pulse", selected: false }, eds.map((e) => ({...e, selected: false})))
        );
      })
    }
  }, [pasted])


  const { setExtraComponent, setExtraNavigation } = useContext(locationContext);
  const { setErrorData } = useContext(alertContext);
  const [nodes, setNodes, onNodesChange] = useNodesState(
    flow.data?.nodes ?? []
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    flow.data?.edges ?? []
  );
  const { setViewport } = useReactFlow();
  const edgeUpdateSuccessful = useRef(true);

  function getId() {
    return `dndnode_` + incrementNodeId();
  }

  useEffect(() => {
    if (reactFlowInstance && flow) {
      flow.data = reactFlowInstance.toObject();
      updateFlow(flow);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges]);
  //update flow when tabs change
  useEffect(() => {
    setNodes(flow?.data?.nodes ?? []);
    setEdges(flow?.data?.edges ?? []);
    if (reactFlowInstance) {
      setViewport(flow?.data?.viewport ?? { x: 1, y: 0, zoom: 0.5 });
    }
  }, [flow, reactFlowInstance, setEdges, setNodes, setViewport]);
  //set extra sidebar
  useEffect(() => {
    setExtraComponent(<ExtraSidebar />);
    setExtraNavigation({ title: "Components" });
  }, [setExtraComponent, setExtraNavigation]);

  const onEdgesChangeMod = useCallback(
    (s: EdgeChange[]) => {
      onEdgesChange(s);
      setNodes((x) => {
        let newX = _.cloneDeep(x);
        return newX;
      });
    },
    [onEdgesChange, setNodes]
  );

  const onConnect = useCallback(
    (params: Connection) => {
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

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      // Get the current bounds of the ReactFlow wrapper element
      const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();

      // Extract the data from the drag event and parse it as a JSON object
      let data: { type: string; node?: APIClassType } = JSON.parse(
        event.dataTransfer.getData("json")
      );

      // If data type is not "chatInput" or if there are no "chatInputNode" nodes present in the ReactFlow instance, create a new node
      if (
        data.type !== "chatInput" ||
        (data.type === "chatInput" &&
          !reactFlowInstance.getNodes().some((n) => n.type === "chatInputNode"))
      ) {
        // Calculate the position where the node should be created
        const position = reactFlowInstance.project({
          x: event.clientX - reactflowBounds.left,
          y: event.clientY - reactflowBounds.top,
        });

        // Generate a unique node ID
        let newId = getId();

        // Create a new node object
        const newNode: NodeType = {
          id: newId,
          type: "genericNode",
          position,
          data: {
            ...data,
            id: newId,
            value: null,
          },
        };

        // Add the new node to the list of nodes in state
        setNodes((nds) => nds.concat(newNode));
      } else {
        // If a chat input node already exists, set an error message
        setErrorData({
          title: "Error creating node",
          list: ["There can't be more than one chat input."],
        });
      }
    },
    // Specify dependencies for useCallback
    [incrementNodeId, reactFlowInstance, setErrorData, setNodes]
  );

  const onDelete = (mynodes) => {
    setEdges(
      edges.filter(
        (ns) => !mynodes.some((n) => ns.source === n.id || ns.target === n.id)
      )
    );
  };

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (isValidConnection(newConnection, reactFlowInstance)) {
        edgeUpdateSuccessful.current = true;
        setEdges((els) => updateEdge(oldEdge, newConnection, els));
      }
    },
    []
  );

	const onEdgeUpdateEnd = useCallback((_, edge) => {
		if (!edgeUpdateSuccessful.current) {
		  setEdges((eds) => eds.filter((e) => e.id !== edge.id));
		}
	
		edgeUpdateSuccessful.current = true;
	  }, []);
	  
	return (
		<div className="w-full h-full" ref={reactFlowWrapper}>
			{Object.keys(templates).length > 0 && Object.keys(types).length > 0 ? (
				<>
					<ReactFlow
						nodes={nodes}
						onMove={() =>
							updateFlow({ ...flow, data: reactFlowInstance.toObject() })
						}
						edges={edges}
						onNodesChange={onNodesChange}
						onEdgesChange={onEdgesChangeMod}
						onConnect={onConnect}
						onLoad={setReactFlowInstance}
						onInit={setReactFlowInstance}
						nodeTypes={nodeTypes}
						onEdgeUpdate={onEdgeUpdate}
						onEdgeUpdateStart={onEdgeUpdateStart}
						onEdgeUpdateEnd={onEdgeUpdateEnd}
						connectionLineComponent={ConnectionLineComponent}
						onDragOver={onDragOver}
						onDrop={onDrop}
						onNodesDelete={onDelete}
            selectNodesOnDrag={false}
					>
						<Background className="dark:bg-gray-900"/>
						<Controls className="[&>button]:text-black  [&>button]:dark:bg-gray-800 hover:[&>button]:dark:bg-gray-700 [&>button]:dark:text-gray-400 [&>button]:dark:fill-gray-400 [&>button]:dark:border-gray-600">
						</Controls>
					</ReactFlow>
					<Chat flow={flow} reactFlowInstance={reactFlowInstance} />
				</>
			) : (
				<></>
			)}
		</div>
	);
}
