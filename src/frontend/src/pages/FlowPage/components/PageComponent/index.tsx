import _, { cloneDeep } from "lodash";
import {
  KeyboardEvent,
  MouseEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useHotkeys } from "react-hotkeys-hook";
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
import {
  INVALID_SELECTION_ERROR_ALERT,
  UPLOAD_ALERT_LIST,
  UPLOAD_ERROR_ALERT,
  WRONG_FILE_ERROR_ALERT,
} from "../../../../constants/alerts_constants";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { FlowType, NodeType } from "../../../../types/flow";
import {
  checkOldComponents,
  generateFlow,
  generateNodeFromFlow,
  getNodeId,
  isValidConnection,
  scapeJSONParse,
  updateIds,
  validateSelection,
} from "../../../../utils/reactflowUtils";
import ConnectionLineComponent from "../ConnectionLineComponent";
import SelectionMenu from "../SelectionMenuComponent";
import getRandomName from "./utils/get-random-name";
import isWrappedWithClass from "./utils/is-wrapped-with-class";

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
    (state) => state.autoSaveCurrentFlow,
  );
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [showCanvas, setSHowCanvas] = useState(
    Object.keys(templates).length > 0 && Object.keys(types).length > 0,
  );

  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const setReactFlowInstance = useFlowStore(
    (state) => state.setReactFlowInstance,
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
    (state) => state.lastCopiedSelection,
  );
  const setLastCopiedSelection = useFlowStore(
    (state) => state.setLastCopiedSelection,
  );
  const onConnect = useFlowStore((state) => state.onConnect);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);
  const edgeUpdateSuccessful = useRef(true);

  const position = useRef({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);

  function handleGroupNode() {
    takeSnapshot();
    if (validateSelection(lastSelection!, edges).length === 0) {
      const clonedNodes = cloneDeep(nodes);
      const clonedEdges = cloneDeep(edges);
      const clonedSelection = cloneDeep(lastSelection);
      updateIds({ nodes: clonedNodes, edges: clonedEdges }, clonedSelection!);
      const { newFlow, removedEdges } = generateFlow(
        clonedSelection!,
        clonedNodes,
        clonedEdges,
        getRandomName(),
      );
      const newGroupNode = generateNodeFromFlow(newFlow, getNodeId);
      // const newEdges = reconnectEdges(newGroupNode, removedEdges);
      setNodes([
        ...clonedNodes.filter(
          (oldNodes) =>
            !clonedSelection?.nodes.some(
              (selectionNode) => selectionNode.id === oldNodes.id,
            ),
        ),
        newGroupNode,
      ]);
      // setEdges([
      //   ...clonedEdges.filter(
      //     (oldEdge) =>
      //       !clonedSelection!.nodes.some(
      //         (selectionNode) =>
      //           selectionNode.id === oldEdge.target ||
      //           selectionNode.id === oldEdge.source,
      //       ),
      //   ),
      //   ...newEdges,
      // ]);
    } else {
      setErrorData({
        title: INVALID_SELECTION_ERROR_ALERT,
        list: validateSelection(lastSelection!, edges),
      });
    }
  }

  const setNode = useFlowStore((state) => state.setNode);
  useEffect(() => {
    const handleMouseMove = (event) => {
      position.current = { x: event.clientX, y: event.clientY };
    };

    document.addEventListener("mousemove", handleMouseMove);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, [lastCopiedSelection, lastSelection, takeSnapshot, selectionMenuVisible]);

  useEffect(() => {
    if (reactFlowInstance && currentFlowId) {
      resetFlow({
        nodes: flow?.data?.nodes ?? [],
        edges: flow?.data?.edges ?? [],
        viewport: flow?.data?.viewport ?? { zoom: 1, x: 0, y: 0 },
      });
    }
  }, [currentFlowId, reactFlowInstance]);

  useEffect(() => {
    if (checkOldComponents({ nodes: flow?.data?.nodes ?? [] })) {
      setNoticeData({
        title:
          "Components created before Langflow 1.0 may be unstable. Ensure components are up to date.",
      });
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanFlow();
    };
  }, []);

  function handleUndo(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      undo();
    }
  }

  function handleRedo(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      redo();
    }
  }

  function handleGroup(e: KeyboardEvent) {
    if (selectionMenuVisible) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      handleGroupNode();
    }
  }

  function handleDuplicate(e: KeyboardEvent) {
    e.preventDefault();
    e.stopPropagation();
    (e as unknown as Event).stopImmediatePropagation();
    const selectedNode = nodes.filter((obj) => obj.selected);
    if (selectedNode.length > 0) {
      paste(
        { nodes: selectedNode, edges: [] },
        {
          x: position.current.x,
          y: position.current.y,
        },
      );
    }
  }

  function handleCopy(e: KeyboardEvent) {
    const multipleSelection = lastSelection?.nodes
      ? lastSelection?.nodes.length > 0
      : false;
    if (
      !isWrappedWithClass(e, "noflow") &&
      (isWrappedWithClass(e, "react-flow__node") || multipleSelection)
    ) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      if (window.getSelection()?.toString().length === 0 && lastSelection) {
        setLastCopiedSelection(_.cloneDeep(lastSelection));
      }
    }
  }

  function handleCut(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      if (window.getSelection()?.toString().length === 0 && lastSelection) {
        setLastCopiedSelection(_.cloneDeep(lastSelection), true);
      }
    }
  }

  function handlePaste(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      if (
        window.getSelection()?.toString().length === 0 &&
        lastCopiedSelection
      ) {
        takeSnapshot();
        paste(lastCopiedSelection, {
          x: position.current.x,
          y: position.current.y,
        });
      }
    }
  }

  function handleDelete(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "nodelete") && lastSelection) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      takeSnapshot();
      deleteNode(lastSelection.nodes.map((node) => node.id));
      deleteEdge(lastSelection.edges.map((edge) => edge.id));
    }
  }

  const undoAction = useShortcutsStore((state) => state.undo);
  const redoAction = useShortcutsStore((state) => state.redo);
  const copyAction = useShortcutsStore((state) => state.copy);
  const duplicate = useShortcutsStore((state) => state.duplicate);
  const deleteAction = useShortcutsStore((state) => state.delete);
  const groupAction = useShortcutsStore((state) => state.group);
  const cutAction = useShortcutsStore((state) => state.cut);
  const pasteAction = useShortcutsStore((state) => state.paste);
  //@ts-ignore
  useHotkeys(undoAction, handleUndo);
  //@ts-ignore
  useHotkeys(redoAction, handleRedo);
  //@ts-ignore
  useHotkeys(groupAction, handleGroup);
  //@ts-ignore
  useHotkeys(duplicate, handleDuplicate);
  //@ts-ignore
  useHotkeys(copyAction, handleCopy);
  //@ts-ignore
  useHotkeys(cutAction, handleCut);
  //@ts-ignore
  useHotkeys(pasteAction, handlePaste);
  //@ts-ignore
  useHotkeys(deleteAction, handleDelete);
  //@ts-ignore
  useHotkeys("delete", handleDelete);

  useEffect(() => {
    setSHowCanvas(
      Object.keys(templates).length > 0 && Object.keys(types).length > 0,
    );
  }, [templates, types]);

  const onConnectMod = useCallback(
    (params: Connection) => {
      takeSnapshot();
      onConnect(params);
    },
    [takeSnapshot, onConnect],
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
          event.dataTransfer.getData("nodedata"),
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
          { x: event.clientX, y: event.clientY },
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
              title: UPLOAD_ERROR_ALERT,
              list: [error],
            });
          });
        } else {
          setErrorData({
            title: WRONG_FILE_ERROR_ALERT,
            list: [UPLOAD_ALERT_LIST],
          });
        }
      }
    },
    // Specify dependencies for useCallback
    [getNodeId, setNodes, takeSnapshot, paste],
  );

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (isValidConnection(newConnection, nodes, edges)) {
        edgeUpdateSuccessful.current = true;
        oldEdge.data.targetHandle = scapeJSONParse(newConnection.targetHandle!);
        oldEdge.data.sourceHandle = scapeJSONParse(newConnection.sourceHandle!);
        setEdges((els) => updateEdge(oldEdge, newConnection, els));
      }
    },
    [setEdges],
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
    [],
  );

  const onPaneClick = useCallback((flow) => {
    setFilterEdge([]);
  }, []);

  function onMouseAction(edge: Edge, color: string): void {
    const edges = useFlowStore.getState().edges;
    const newEdges = _.cloneDeep(edges);
    const style = { stroke: color, transition: "stroke 0.25s" };
    const updatedEdges = newEdges.map((obj) => {
      if (obj.id === edge.id) {
        return { ...obj, style };
      }
      return obj;
    });
    setEdges(updatedEdges);
  }

  return (
    <div className="h-full w-full" ref={reactFlowWrapper}>
      {showCanvas ? (
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
            panActivationKeyCode={""}
            proOptions={{ hideAttribution: true }}
            onPaneClick={onPaneClick}
          >
            <Background className="" />
            {!view && (
              <Controls className="fill-foreground stroke-foreground text-primary [&>button]:border-b-border [&>button]:bg-muted hover:[&>button]:bg-border"></Controls>
            )}
            <SelectionMenu
              lastSelection={lastSelection}
              isVisible={selectionMenuVisible}
              nodes={lastSelection?.nodes}
              onClick={() => {
                handleGroupNode();
              }}
            />
          </ReactFlow>
        </div>
      ) : (
        <></>
      )}
    </div>
  );
}
