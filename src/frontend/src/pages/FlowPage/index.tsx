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
import { isValidConnection } from "../../utils";
import useUndoRedo from "./hooks/useUndoRedo";

const nodeTypes = {
  genericNode: GenericNode,
};

export default function FlowPage({ flow }: { flow: FlowType }) {
  let { updateFlow, disableCopyPaste, addFlow, getNodeId, paste } =
    useContext(TabsContext);
  const { types, reactFlowInstance, setReactFlowInstance, templates } =
    useContext(typesContext);
  const reactFlowWrapper = useRef(null);

  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo();

  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams>(null);

  const [lastCopiedSelection, setLastCopiedSelection] = useState(null);

  useEffect(() => {
    // this effect is used to attach the global event handlers

    const onKeyDown = (event: KeyboardEvent) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key === "c" &&
        lastSelection &&
        !disableCopyPaste
      ) {
        event.preventDefault();
        setLastCopiedSelection(_.cloneDeep(lastSelection));
      }
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key === "v" &&
        lastCopiedSelection &&
        !disableCopyPaste
      ) {
        event.preventDefault();
        let bounds = reactFlowWrapper.current.getBoundingClientRect();
        paste(lastCopiedSelection, {
          x: position.x - bounds.left,
          y: position.y - bounds.top,
        });
      }
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key === "g" &&
        lastSelection
      ) {
        event.preventDefault();
        // addFlow(newFlow, false);
      }
    };
    const handleMouseMove = (event) => {
      setPosition({ x: event.clientX, y: event.clientY });
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousemove", handleMouseMove);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, [position, lastCopiedSelection, lastSelection]);

  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);

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
        addEdge(
          {
            ...params,
            style: { stroke: "inherit" },
            className:
              params.targetHandle.split("|")[0] === "Text"
                ? "stroke-gray-800 dark:stroke-gray-300"
                : "stroke-gray-900 dark:stroke-gray-200",
            animated: params.targetHandle.split("|")[0] === "Text",
          },
          eds
        )
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
  }, []);
  const onSelectionStart = useCallback(() => {
    setSelectionEnded(false);
  }, []);

  // Workaround to show the menu only after the selection has ended.
  useEffect(() => {
    if (selectionEnded && lastSelection && lastSelection.nodes.length > 1) {
      setSelectionMenuVisible(true);
    } else {
      setSelectionMenuVisible(false);
    }
  }, [selectionEnded, lastSelection]);

  const onSelectionChange = useCallback((flow) => {
    setLastSelection(flow);
  }, []);

  const { setDisableCopyPaste } = useContext(TabsContext);

  return (
    <div className="w-full h-full" ref={reactFlowWrapper}>
      {Object.keys(templates).length > 0 && Object.keys(types).length > 0 ? (
        <>
          <ReactFlow
            nodes={nodes}
            onMove={() => {
              updateFlow({ ...flow, data: reactFlowInstance.toObject() });
            }}
            edges={edges}
            onPaneClick={() => {
              setDisableCopyPaste(false);
            }}
            onPaneMouseLeave={() => {
              setDisableCopyPaste(true);
            }}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChangeMod}
            onConnect={onConnect}
            disableKeyboardA11y={true}
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
            nodesDraggable={!disableCopyPaste}
            panOnDrag={!disableCopyPaste}
            zoomOnDoubleClick={!disableCopyPaste}
            selectNodesOnDrag={false}
            className="theme-attribution"
          >
            <Background className="dark:bg-gray-900" />
            <Controls className="[&>button]:text-black  [&>button]:dark:bg-gray-800 hover:[&>button]:dark:bg-gray-700 [&>button]:dark:text-gray-400 [&>button]:dark:fill-gray-400 [&>button]:dark:border-gray-600"></Controls>
          </ReactFlow>
          <Chat flow={flow} reactFlowInstance={reactFlowInstance} />
        </>
      ) : (
        <></>
      )}
    </div>
  );
}
