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
  NodeDragHandler,
  OnEdgesDelete,
  OnNodesDelete,
  SelectionDragHandler,
  useOnViewportChange,
  OnSelectionChangeParams,
  OnNodesChange,
} from "reactflow";
import _ from "lodash";
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
import { filterFlow, generateFlow, generateNodeFromFlow, getMiddlePoint, isValidConnection } from "../../utils";
import useUndoRedo from "./hooks/useUndoRedo";
import SelectionMenu from "./components/SelectionMenuComponent";
import GroupNode from "../../CustomNodes/GroupNode";

const nodeTypes = {
  genericNode: GenericNode,
  groupNode: GroupNode
};

export default function FlowPage({ flow }: { flow: FlowType }) {
  let { updateFlow, disableCP, addFlow, getNodeId} =
    useContext(TabsContext);
  const { types, reactFlowInstance, setReactFlowInstance, templates } =
    useContext(typesContext);
  const reactFlowWrapper = useRef(null);

  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo();

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if ((event.ctrlKey || event.metaKey) && (event.key === 'c') && lastSelection && !disableCP) {
      event.preventDefault();
      setLastCopiedSelection(lastSelection);
    }
    if ((event.ctrlKey || event.metaKey) && (event.key === 'v') && lastCopiedSelection && !disableCP) {
      event.preventDefault();
      paste();
    }
    if ((event.ctrlKey || event.metaKey) && (event.key === 'g') && lastSelection) {
      event.preventDefault();
      // addFlow(newFlow, false);
    }


  }

  const [lastSelection, setLastSelection] = useState<OnSelectionChangeParams>(null);
  const [lastCopiedSelection, setLastCopiedSelection] = useState(null);

  const [position, setPosition] = useState({ x: 0, y: 0 });

  const [selectionMenuPosition, setSelectionMenuPosition] = useState({
    x: 0,
    y: 0,
  });
  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);

  const handleMouseMove = (event) => {
    setPosition({ x: event.clientX, y: event.clientY });
  };

  let paste = () => {
    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    lastCopiedSelection.nodes.forEach((n) => {
      if (n.position.y < minimumY) {
        minimumY = n.position.y;
      }
      if (n.position.x < minimumX) {
        minimumX = n.position.x;
      }
    });

    const bounds = reactFlowWrapper.current.getBoundingClientRect();
    const insidePosition = reactFlowInstance.project({
      x: position.x - bounds.left,
      y: position.y - bounds.top,
    });

    lastCopiedSelection.nodes.forEach((n) => {
      // Generate a unique node ID
      let newId = getNodeId();
      idsMap[n.id] = newId;

      // Create a new node object
      const newNode: NodeType = {
        id: newId,
        type: "genericNode",
        position: {
          x: insidePosition.x + n.position.x - minimumX,
          y: insidePosition.y + n.position.y - minimumY,
        },
        data: {
          ...n.data,
          id: newId,
        },
      };

      // Add the new node to the list of nodes in state
      setNodes((nds) =>
        nds
          .map((e) => ({ ...e, selected: false }))
          .concat({ ...newNode, selected: false })
      );
    });

    lastCopiedSelection.edges.forEach((e) => {
      let source = idsMap[e.source];
      let target = idsMap[e.target];
      let sourceHandleSplitted = e.sourceHandle.split("|");
      let sourceHandle =
        sourceHandleSplitted[0] +
        "|" +
        source +
        "|" +
        sourceHandleSplitted.slice(2).join("|");
      let targetHandleSplitted = e.targetHandle.split("|");
      let targetHandle =
        targetHandleSplitted.slice(0, -1).join("|") + "|" + target;
      let id =
        "reactflow__edge-" +
        source +
        sourceHandle +
        "-" +
        target +
        targetHandle;
      setEdges((eds) =>
        addEdge(
          {
            source,
            target,
            sourceHandle,
            targetHandle,
            id,
            className: "animate-pulse",
            selected: false,
          },
          eds.map((e) => ({ ...e, selected: false }))
        )
      );
    });
  };

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
			takeSnapshot();
			setEdges((eds) =>
				addEdge({ ...params, style:params.targetHandle.split('|')[0] === "Text" ? {stroke: "#333333", strokeWidth: 2} : {stroke: "#222222"}, className:(params.targetHandle.split('|')[0] === "Text" ? "" : "animate-pulse"), animated:(params.targetHandle.split('|')[0] === "Text") }, eds)
			);
			setNodes((x) => {
				let newX = _.cloneDeep(x);
				return newX;
			});
		},
		[setEdges, setNodes, takeSnapshot]
	);

  const onNodeDragStart: NodeDragHandler = useCallback(() => {
    // 👇 make dragging a node undoable
    takeSnapshot();
    // 👉 you can place your event handlers here
  }, [takeSnapshot]);

  const onSelectionDragStart: SelectionDragHandler = useCallback(() => {
    // 👇 make dragging a selection undoable
    takeSnapshot();
  }, [takeSnapshot]);

  const onEdgesDelete: OnEdgesDelete = useCallback(() => {
    // 👇 make deleting edges undoable
    takeSnapshot();
  }, [takeSnapshot]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      takeSnapshot();

      // Get the current bounds of the ReactFlow wrapper element
      const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();

      // Extract the data from the drag event and parse it as a JSON object
      let data: { type: string; node?: APIClassType } = JSON.parse(
        event.dataTransfer.getData("json")
      );

      // If data type is not "chatInput" or if there are no "chatInputNode" nodes present in the ReactFlow instance, create a new node
      // Calculate the position where the node should be created
      const position = reactFlowInstance.project({
        x: event.clientX - reactflowBounds.left,
        y: event.clientY - reactflowBounds.top,
      });

      // Generate a unique node ID
      let newId = getNodeId();
      let newNode: NodeType;

      if (data.type !== "groupNode") {


        // Create a new node object
        newNode = {
          id: newId,
          type: "genericNode",
          position,
          data: {
            ...data,
            id: newId,
            value: null,
          },
        };
      } else {
        // Create a new node object
        newNode = {
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

      }
      setNodes((nds) => nds.concat(newNode));
    },
    // Specify dependencies for useCallback
    [getNodeId, reactFlowInstance, setErrorData, setNodes, takeSnapshot]
  );

  const onDelete = useCallback(
    (mynodes) => {
      takeSnapshot();
      setEdges(
        edges.filter(
          (ns) => !mynodes.some((n) => ns.source === n.id || ns.target === n.id)
        )
      );
    },
    [takeSnapshot, edges, setEdges]
  );

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

  const [selectionEnded, setSelectionEnded] = useState(false);

  const onSelectionEnd = useCallback(() => {
    setSelectionEnded(true);
  }, [])
  const onSelectionStart = useCallback(() => {
    setSelectionEnded(false);
  }, [])

  // Workaround to show the menu only after the selection has ended.
  useEffect(() => {
    if (selectionEnded && lastSelection && lastSelection.nodes.length > 1) {
      setSelectionMenuVisible(true);
    } else {
      setSelectionMenuVisible(false);
    }
  }, [selectionEnded, lastSelection])


  const onSelectionChange = useCallback((flow) => {
    setLastSelection(flow);
  }, []);

  return (
    <div
      className="w-full h-full"
      onMouseMove={handleMouseMove}
      ref={reactFlowWrapper}
    >
      {Object.keys(templates).length > 0 && Object.keys(types).length > 0 ? (
        <>
          <ReactFlow
            nodes={nodes}
            onMove={() => {
              updateFlow({ ...flow, data: reactFlowInstance.toObject() });
            }}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChangeMod}
            onKeyDown={(e) => onKeyDown(e)}
            onConnect={onConnect}
            onLoad={setReactFlowInstance}
            onInit={setReactFlowInstance}
            nodeTypes={nodeTypes}
            onEdgeUpdate={onEdgeUpdate}
            onEdgeUpdateStart={onEdgeUpdateStart}
            onEdgeUpdateEnd={onEdgeUpdateEnd}
            onNodeDragStart={onNodeDragStart}
            onSelectionDragStart={onSelectionDragStart}
            onSelectionEnd={onSelectionEnd}
            onSelectionStart={onSelectionStart}
            onEdgesDelete={onEdgesDelete}
            connectionLineComponent={ConnectionLineComponent}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodesDelete={onDelete}
            onSelectionChange={onSelectionChange}
            selectNodesOnDrag={false}
          >
            <Background className="dark:bg-gray-900" />
            <Controls className="[&>button]:text-black  [&>button]:dark:bg-gray-800 hover:[&>button]:dark:bg-gray-700 [&>button]:dark:text-gray-400 [&>button]:dark:fill-gray-400 [&>button]:dark:border-gray-600"></Controls>
          </ReactFlow>
          <Chat flow={flow} reactFlowInstance={reactFlowInstance} />
          <SelectionMenu
            onClick={() => {
              console.log(lastSelection);
              console.log(getMiddlePoint(lastSelection.nodes));
              console.log(reactFlowInstance.getViewport());
              const newFlow = generateFlow(lastSelection, reactFlowInstance, "new component");
              const newGroupNode = generateNodeFromFlow(newFlow)
              setNodes(oldNodes => [...oldNodes.filter((oldNode) => !lastSelection.nodes.some(selectionNode => selectionNode.id === oldNode.id)), newGroupNode])
              setEdges(oldEdges => oldEdges.filter((oldEdge) => !lastSelection.nodes.some(selectionNode => selectionNode.id === oldEdge.target || selectionNode.id === oldEdge.source)))
            }}
            isVisible={selectionMenuVisible}
            nodes={
              lastSelection?.nodes
            }
          />
        </>
      ) : (
        <></>
      )}
    </div>
  );
}
