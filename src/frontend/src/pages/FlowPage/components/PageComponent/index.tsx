import _ from "lodash";
import { MouseEvent, useCallback, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Connection,
  Controls,
  Edge,
  NodeDragHandler,
  OnMove,
  OnSelectionChangeParams,
  SelectionDragHandler,
  updateEdge,
} from "reactflow";
import GenericNode from "../../../../CustomNodes/GenericNode";
import Chat from "../../../../components/chatComponent";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { FlowType, NodeType } from "../../../../types/flow";
import {
  generateFlow,
  generateNodeFromFlow,
  getNodeId,
  isValidConnection,
  validateSelection,
} from "../../../../utils/reactflowUtils";
import { getRandomName, isWrappedWithClass } from "../../../../utils/utils";
import ConnectionLineComponent from "../ConnectionLineComponent";
import SelectionMenu from "../SelectionMenuComponent";
import ExtraSidebar from "../extraSidebarComponent";

const nodeTypes = {
  genericNode: GenericNode,
};

export default function Page({
  flow,
  view,
}: {
  flow: FlowType;
  view?: boolean;
}): JSX.Element {
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const autoSaveCurrentFlow = useFlowsManagerStore(
    (state) => state.autoSaveCurrentFlow
  );
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const setReactFlowInstance = useFlowStore(
    (state) => state.setReactFlowInstance
  );

  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const onNodesChange = useFlowStore((state) => state.onNodesChange);
  const onEdgesChange = useFlowStore((state) => state.onEdgesChange);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const cleanFlow = useFlowStore((state) => state.cleanFlow);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const deleteEdge = useFlowStore((state) => state.deleteEdge);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const paste = useFlowStore((state) => state.paste);
  const resetFlow = useFlowStore((state) => state.resetFlow);
  const lastCopiedSelection = useFlowStore(
    (state) => state.lastCopiedSelection
  );
  const setLastCopiedSelection = useFlowStore(
    (state) => state.setLastCopiedSelection
  );
  const onConnect = useFlowStore((state) => state.onConnect);

  const position = useRef({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!isWrappedWithClass(event, "noundo")) {
        if (
          (event.key === "y" || (event.key === "z" && event.shiftKey)) &&
          (event.ctrlKey || event.metaKey)
        ) {
          event.preventDefault(); // prevent the default action
          redo();
        } else if (event.key === "z" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          undo();
        }
      }
      if (
        !isWrappedWithClass(event, "nocopy") &&
        window.getSelection()?.toString().length === 0
      ) {
        if (
          (event.ctrlKey || event.metaKey) &&
          event.key === "c" &&
          lastSelection
        ) {
          event.preventDefault();
          setLastCopiedSelection(_.cloneDeep(lastSelection));
        } else if (
          (event.ctrlKey || event.metaKey) &&
          event.key === "v" &&
          lastCopiedSelection
        ) {
          event.preventDefault();
          takeSnapshot();
          paste(lastCopiedSelection, {
            x: position.current.x,
            y: position.current.y,
          });
        } else if (
          (event.ctrlKey || event.metaKey) &&
          event.key === "g" &&
          lastSelection
        ) {
          event.preventDefault();
        }
      }
      if (!isWrappedWithClass(event, "nodelete")) {
        if (
          (event.key === "Delete" || event.key === "Backspace") &&
          lastSelection
        ) {
          event.preventDefault();
          takeSnapshot();
          deleteNode(lastSelection.nodes.map((node) => node.id));
          deleteEdge(lastSelection.edges.map((edge) => edge.id));
        }
      }
    };

    const handleMouseMove = (event) => {
      position.current = { x: event.clientX, y: event.clientY };
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousemove", handleMouseMove);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, [lastCopiedSelection, lastSelection, takeSnapshot]);

  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const edgeUpdateSuccessful = useRef(true);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  useEffect(() => {
    if (reactFlowInstance) {
      resetFlow({
        nodes: flow?.data?.nodes ?? [],
        edges: flow?.data?.edges ?? [],
        viewport: flow?.data?.viewport ?? { zoom: 1, x: 0, y: 0 },
      });
    }
  }, [currentFlowId, reactFlowInstance]);

  useEffect(() => {
    return () => {
      cleanFlow();
    };
  }, []);

  const onConnectMod = useCallback(
    (params: Connection) => {
      takeSnapshot();
      onConnect(params);
    },
    [takeSnapshot, onConnect]
  );

  const onNodeDragStart: NodeDragHandler = useCallback(() => {
    // 👇 make dragging a node undoable
    takeSnapshot();
    // 👉 you can place your event handlers here
  }, [takeSnapshot]);

  const onNodeDragStop: NodeDragHandler = useCallback(() => {
    autoSaveCurrentFlow(nodes, edges, reactFlowInstance?.getViewport()!);
    // 👉 you can place your event handlers here
  }, [takeSnapshot, autoSaveCurrentFlow, nodes, edges, reactFlowInstance]);

  const onMoveEnd: OnMove = useCallback(() => {
    // 👇 make moving the canvas undoable
    autoSaveCurrentFlow(nodes, edges, reactFlowInstance?.getViewport()!);
  }, [takeSnapshot, autoSaveCurrentFlow, nodes, edges, reactFlowInstance]);

  const onSelectionDragStart: SelectionDragHandler = useCallback(() => {
    // 👇 make dragging a selection undoable
    takeSnapshot();
  }, [takeSnapshot]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    if (event.dataTransfer.types.some((types) => types === "nodedata")) {
      event.dataTransfer.dropEffect = "move";
    } else {
      event.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (event.dataTransfer.types.some((types) => types === "nodedata")) {
        takeSnapshot();

        // Extract the data from the drag event and parse it as a JSON object
        const data: { type: string; node?: APIClassType } = JSON.parse(
          event.dataTransfer.getData("nodedata")
        );

        const newId = getNodeId(data.type);

        const newNode: NodeType = {
          id: newId,
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: {
            ...data,
            id: newId,
          },
        };
        paste(
          { nodes: [newNode], edges: [] },
          { x: event.clientX, y: event.clientY }
        );
      } else if (event.dataTransfer.types.some((types) => types === "Files")) {
        takeSnapshot();
        if (event.dataTransfer.files.item(0)!.type === "application/json") {
          const position = {
            x: event.clientX,
            y: event.clientY,
          };
          uploadFlow({
            newProject: false,
            isComponent: false,
            file: event.dataTransfer.files.item(0)!,
            position: position,
          }).catch((error) => {
            setErrorData({
              title: "Error uploading file",
              list: [error],
            });
          });
        } else {
          setErrorData({
            title: "Invalid file type",
            list: ["Please upload a JSON file"],
          });
        }
      }
    },
    // Specify dependencies for useCallback
    [getNodeId, setNodes, takeSnapshot, paste]
  );

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (isValidConnection(newConnection, nodes, edges)) {
        edgeUpdateSuccessful.current = true;
        setEdges((els) => updateEdge(oldEdge, newConnection, els));
      }
    },
    [setEdges]
  );

  const onEdgeUpdateEnd = useCallback((_, edge: Edge): void => {
    if (!edgeUpdateSuccessful.current) {
      setEdges((eds) => eds.filter((edg) => edg.id !== edge.id));
    }
    edgeUpdateSuccessful.current = true;
  }, []);

  const [selectionEnded, setSelectionEnded] = useState(true);

  const onSelectionEnd = useCallback(() => {
    setSelectionEnded(true);
  }, []);
  const onSelectionStart = useCallback((event: MouseEvent) => {
    event.preventDefault();
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

  const onSelectionChange = useCallback(
    (flow: OnSelectionChangeParams): void => {
      setLastSelection(flow);
    },
    []
  );

  const onPaneClick = useCallback((flow) => {
    setFilterEdge([]);
  }, []);

  return (
    <div className="flex h-full overflow-hidden">
      {!view && <ExtraSidebar />}
      {/* Main area */}
      <main className="flex flex-1">
        {/* Primary column */}
        <div className="h-full w-full">
          <div className="h-full w-full" ref={reactFlowWrapper}>
            {Object.keys(templates).length > 0 &&
            Object.keys(types).length > 0 ? (
              <div id="react-flow-id" className="h-full w-full">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnectMod}
                  disableKeyboardA11y={true}
                  onInit={setReactFlowInstance}
                  nodeTypes={nodeTypes}
                  onEdgeUpdate={onEdgeUpdate}
                  onEdgeUpdateStart={onEdgeUpdateStart}
                  onEdgeUpdateEnd={onEdgeUpdateEnd}
                  onNodeDragStart={onNodeDragStart}
                  onNodeDragStop={onNodeDragStop}
                  onSelectionDragStart={onSelectionDragStart}
                  onSelectionEnd={onSelectionEnd}
                  onSelectionStart={onSelectionStart}
                  connectionLineComponent={ConnectionLineComponent}
                  onDragOver={onDragOver}
                  onMoveEnd={onMoveEnd}
                  onDrop={onDrop}
                  onSelectionChange={onSelectionChange}
                  deleteKeyCode={[]}
                  className="theme-attribution"
                  minZoom={0.01}
                  maxZoom={8}
                  zoomOnScroll={!view}
                  zoomOnPinch={!view}
                  panOnDrag={!view}
                  proOptions={{ hideAttribution: true }}
                  onPaneClick={onPaneClick}
                >
                  <Background className="" />
                  {!view && (
                    <Controls
                      className="bg-muted fill-foreground stroke-foreground text-primary
                   [&>button]:border-b-border hover:[&>button]:bg-border"
                    ></Controls>
                  )}
                  <SelectionMenu
                    isVisible={selectionMenuVisible}
                    nodes={lastSelection?.nodes}
                    onClick={() => {
                      takeSnapshot();
                      if (
                        validateSelection(lastSelection!, edges).length === 0
                      ) {
                        const { newFlow } = generateFlow(
                          lastSelection!,
                          nodes,
                          edges,
                          getRandomName()
                        );
                        const newGroupNode = generateNodeFromFlow(
                          newFlow,
                          getNodeId
                        );
                        setNodes((oldNodes) => [
                          ...oldNodes.filter(
                            (oldNodes) =>
                              !lastSelection?.nodes.some(
                                (selectionNode) =>
                                  selectionNode.id === oldNodes.id
                              )
                          ),
                          newGroupNode,
                        ]);
                        setEdges((oldEdges) =>
                          oldEdges.filter(
                            (oldEdge) =>
                              !lastSelection!.nodes.some(
                                (selectionNode) =>
                                  selectionNode.id === oldEdge.target ||
                                  selectionNode.id === oldEdge.source
                              )
                          )
                        );
                      } else {
                        setErrorData({
                          title: "Invalid selection",
                          list: validateSelection(lastSelection!, edges),
                        });
                      }
                    }}
                  />
                </ReactFlow>
                {!view && <Chat flow={flow} />}
              </div>
            ) : (
              <></>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
