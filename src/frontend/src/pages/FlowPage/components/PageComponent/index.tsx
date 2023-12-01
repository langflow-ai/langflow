import _ from "lodash";
import {
  MouseEvent,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import ReactFlow, {
  Background,
  Connection,
  Controls,
  Edge,
  EdgeChange,
  NodeChange,
  NodeDragHandler,
  OnSelectionChangeParams,
  SelectionDragHandler,
  addEdge,
  updateEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "reactflow";
import GenericNode from "../../../../CustomNodes/GenericNode";
import Chat from "../../../../components/chatComponent";
import { alertContext } from "../../../../contexts/alertContext";
import { FlowsContext } from "../../../../contexts/flowsContext";
import { locationContext } from "../../../../contexts/locationContext";
import { typesContext } from "../../../../contexts/typesContext";
import { undoRedoContext } from "../../../../contexts/undoRedoContext";
import { APIClassType } from "../../../../types/api";
import { FlowType, NodeType, targetHandleType } from "../../../../types/flow";
import { FlowsState } from "../../../../types/tabs";
import {
  generateFlow,
  generateNodeFromFlow,
  isValidConnection,
  scapeJSONParse,
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
  let {
    updateFlow,
    uploadFlow,
    addFlow,
    getNodeId,
    paste,
    lastCopiedSelection,
    setLastCopiedSelection,
    tabsState,
    saveFlow,
    setTabsState,
    tabId,
    flows,
  } = useContext(FlowsContext);
  const {
    types,
    reactFlowInstance,
    setReactFlowInstance,
    templates,
    setFilterEdge,
    deleteNode,
    deleteEdge,
  } = useContext(typesContext);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const { takeSnapshot } = useContext(undoRedoContext);

  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!isWrappedWithClass(event, "nocopy")) {
        if (
          (event.ctrlKey || event.metaKey) &&
          event.key === "c" &&
          lastSelection
        ) {
          event.preventDefault();
          setLastCopiedSelection(_.cloneDeep(lastSelection));
        }
        if (
          (event.ctrlKey || event.metaKey) &&
          event.key === "v" &&
          lastCopiedSelection
        ) {
          event.preventDefault();
          paste(lastCopiedSelection, {
            x: position.x,
            y: position.y,
          });
        }
        if (
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

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [lastCopiedSelection, lastSelection]);

  useEffect(() => {
    const handleMouseMove = (event) => {
      setPosition({ x: event.clientX, y: event.clientY });
    };

    document.addEventListener("mousemove", handleMouseMove);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, [position]);

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

  //update flow when tabs change
  useEffect(() => {
    setNodes(flow?.data?.nodes ?? []);
    setEdges(flow?.data?.edges ?? []);
  }, [flow, reactFlowInstance]);

  useEffect(() => {
    const index = flows.findIndex((flowId) => flowId.id === flow.id);

    const interval = setInterval(() => {
      saveFlow(
        {
          ...flows[index]!,
          data: reactFlowInstance ? reactFlowInstance!.toObject() : flow!.data,
        },
        true
      );
    }, 30000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  //remove this if you dont want to see the whole flow on fork
  useEffect(() => {
    setTimeout(() => {
      flow?.data!.nodes!.length > 3
        ? reactFlowInstance?.fitView({ padding: 0.1 })
        : reactFlowInstance?.fitView({ padding: 0.5 });
    }, 200);
  }, []);

  const onEdgesChangeMod = useCallback(
    (change: EdgeChange[]) => {
      updateFlow({
        ...flow!,
        data: reactFlowInstance ? reactFlowInstance!.toObject() : flow!.data,
      });
      onEdgesChange(change);
      //@ts-ignore
      setTabsState((prev: FlowsState) => {
        return {
          ...prev,
          [tabId]: {
            ...prev[tabId],
            isPending: true,
          },
        };
      });
    },
    [onEdgesChange, setNodes, setTabsState, tabId]
  );

  const onNodesChangeMod = useCallback(
    (change: NodeChange[]) => {
      onNodesChange(change);
      //@ts-ignore
      setTabsState((prev: FlowsState) => {
        return {
          ...prev,
          [tabId]: {
            ...prev[tabId],
            isPending: true,
          },
        };
      });
    },
    [onNodesChange, setTabsState, tabId]
  );

  const onConnect = useCallback(
    (params: Connection) => {
      takeSnapshot();
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            data: {
              targetHandle: scapeJSONParse(params.targetHandle!),
              sourceHandle: scapeJSONParse(params.sourceHandle!),
            },
            style: { stroke: "#555" },
            className:
              ((scapeJSONParse(params.targetHandle!) as targetHandleType)
                .type === "Text"
                ? "stroke-foreground "
                : "stroke-foreground ") + " stroke-connection",
            animated:
              (scapeJSONParse(params.targetHandle!) as targetHandleType)
                .type === "Text",
          },
          eds
        )
      );
      setNodes((node) => {
        let newX = _.cloneDeep(node);
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

        // Get the current bounds of the ReactFlow wrapper element
        const reactflowBounds =
          reactFlowWrapper.current?.getBoundingClientRect();

        // Extract the data from the drag event and parse it as a JSON object
        let data: { type: string; node?: APIClassType } = JSON.parse(
          event.dataTransfer.getData("nodedata")
        );

        // Calculate the position where the node should be created
        const position = reactFlowInstance!.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        // Generate a unique node ID
        let { type } = data;
        let newId = getNodeId(type);
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
            },
          };

          // Add the new node to the list of nodes in state
        }
        setNodes((nds) => nds.concat(newNode));
      } else if (event.dataTransfer.types.some((types) => types === "Files")) {
        takeSnapshot();
        if (event.dataTransfer.files.item(0)!.type === "application/json") {
          uploadFlow({
            newProject: false,
            isComponent: false,
            file: event.dataTransfer.files.item(0)!,
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
    [getNodeId, reactFlowInstance, setNodes, takeSnapshot]
  );

  useEffect(() => {
    setExtraComponent(<ExtraSidebar />);
    setExtraNavigation({ title: "Components" });

    return () => {
      if (tabsState && tabsState[flow.id]?.isPending) {
        saveFlow({
          ...flow!,
          data: reactFlowInstance ? reactFlowInstance!.toObject() : flow!.data,
        });
      }
    };
  }, []);

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (isValidConnection(newConnection, reactFlowInstance!)) {
        edgeUpdateSuccessful.current = true;
        setEdges((els) => updateEdge(oldEdge, newConnection, els));
      }
    },
    [reactFlowInstance, setEdges]
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
                  onMove={() => {
                    if (reactFlowInstance)
                      updateFlow({
                        ...flow,
                        data: reactFlowInstance.toObject(),
                      });
                  }}
                  edges={edges}
                  onNodesChange={onNodesChangeMod}
                  onEdgesChange={onEdgesChangeMod}
                  onConnect={onConnect}
                  disableKeyboardA11y={true}
                  onInit={setReactFlowInstance}
                  nodeTypes={nodeTypes}
                  onEdgeUpdate={onEdgeUpdate}
                  onEdgeUpdateStart={onEdgeUpdateStart}
                  onEdgeUpdateEnd={onEdgeUpdateEnd}
                  onNodeDragStart={onNodeDragStart}
                  onSelectionDragStart={onSelectionDragStart}
                  onSelectionEnd={onSelectionEnd}
                  onSelectionStart={onSelectionStart}
                  connectionLineComponent={ConnectionLineComponent}
                  onDragOver={onDragOver}
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
                          reactFlowInstance!,
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
                {!view && (
                  <Chat flow={flow} reactFlowInstance={reactFlowInstance!} />
                )}
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
