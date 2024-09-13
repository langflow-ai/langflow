import { DefaultEdge } from "@/CustomEdges";
import NoteNode from "@/CustomNodes/NoteNode";
import IconComponent from "@/components/genericIconComponent";
import LoadingComponent from "@/components/loadingComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { useGetBuildsQuery } from "@/controllers/API/queries/_builds";
import { track } from "@/customization/utils/analytics";
import useAutoSaveFlow from "@/hooks/flows/use-autosave-flow";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { getNodeRenderType, isSupportedNodeTypes } from "@/utils/utils";

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
  ControlButton,
  Controls,
  Edge,
  NodeDragHandler,
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
import { NodeType } from "../../../../types/flow";
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
  noteNode: NoteNode,
};

export default function Page({ view }: { view?: boolean }): JSX.Element {
  const uploadFlow = useUploadFlow();
  const autoSaveFlow = useAutoSaveFlow();
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

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
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const deleteEdge = useFlowStore((state) => state.deleteEdge);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const paste = useFlowStore((state) => state.paste);
  const lastCopiedSelection = useFlowStore(
    (state) => state.lastCopiedSelection,
  );
  const setLastCopiedSelection = useFlowStore(
    (state) => state.setLastCopiedSelection,
  );
  const onConnect = useFlowStore((state) => state.onConnect);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const updateCurrentFlow = useFlowStore((state) => state.updateCurrentFlow);
  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);
  const edgeUpdateSuccessful = useRef(true);

  const position = useRef({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  function handleGroupNode() {
    takeSnapshot();
    if (validateSelection(lastSelection!, edges).length === 0) {
      const clonedNodes = cloneDeep(nodes);
      const clonedEdges = cloneDeep(edges);
      const clonedSelection = cloneDeep(lastSelection);
      updateIds({ nodes: clonedNodes, edges: clonedEdges }, clonedSelection!);
      const { newFlow } = generateFlow(
        clonedSelection!,
        clonedNodes,
        clonedEdges,
        getRandomName(),
      );

      const newGroupNode = generateNodeFromFlow(newFlow, getNodeId);

      setNodes([
        ...clonedNodes.filter(
          (oldNodes) =>
            !clonedSelection?.nodes.some(
              (selectionNode) => selectionNode.id === oldNodes.id,
            ),
        ),
        newGroupNode,
      ]);
    } else {
      setErrorData({
        title: INVALID_SELECTION_ERROR_ALERT,
        list: validateSelection(lastSelection!, edges),
      });
    }
  }

  useEffect(() => {
    const handleMouseMove = (event) => {
      position.current = { x: event.clientX, y: event.clientY };
    };

    document.addEventListener("mousemove", handleMouseMove);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, [lastCopiedSelection, lastSelection, takeSnapshot, selectionMenuVisible]);

  const { isFetching } = useGetBuildsQuery({ flowId: currentFlowId });

  const showCanvas =
    Object.keys(templates).length > 0 &&
    Object.keys(types).length > 0 &&
    !isFetching;

  useEffect(() => {
    if (checkOldComponents({ nodes })) {
      setNoticeData({
        title:
          "Components created before Langflow 1.0 may be unstable. Ensure components are up to date.",
      });
    }
  }, [currentFlowId]);

  useEffect(() => {
    useFlowStore.setState({ autoSaveFlow });
  });

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

  const onConnectMod = useCallback(
    (params: Connection) => {
      takeSnapshot();
      onConnect(params);
      track("New Component Connection Added");
    },
    [takeSnapshot, onConnect],
  );

  const onNodeDragStart: NodeDragHandler = useCallback(() => {
    // 👇 make dragging a node undoable
    takeSnapshot();
    // 👉 you can place your event handlers here
  }, [takeSnapshot]);

  const onNodeDragStop: NodeDragHandler = useCallback(() => {
    // 👇 make moving the canvas undoable
    autoSaveFlow();
    updateCurrentFlow({ nodes });
  }, [takeSnapshot, autoSaveFlow, nodes, edges, reactFlowInstance]);

  const onSelectionDragStart: SelectionDragHandler = useCallback(() => {
    // 👇 make dragging a selection undoable
    takeSnapshot();
  }, [takeSnapshot]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    if (event.dataTransfer.types.some((types) => isSupportedNodeTypes(types))) {
      event.dataTransfer.dropEffect = "move";
    } else {
      event.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (event.dataTransfer.types.some((type) => isSupportedNodeTypes(type))) {
        takeSnapshot();

        const datakey = event.dataTransfer.types.find((type) =>
          isSupportedNodeTypes(type),
        );

        // Extract the data from the drag event and parse it as a JSON object
        const data: { type: string; node?: APIClassType } = JSON.parse(
          event.dataTransfer.getData(datakey!),
        );

        track(`Component Added: ${data.node?.display_name}`);

        const newId = getNodeId(data.type);

        const newNode: NodeType = {
          id: newId,
          type: getNodeRenderType(datakey!),
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
        const position = {
          x: event.clientX,
          y: event.clientY,
        };
        uploadFlow({
          files: Array.from(event.dataTransfer.files!),
          position: position,
        }).catch((error) => {
          setErrorData({
            title: UPLOAD_ERROR_ALERT,
            list: [(error as Error).message],
          });
        });
      } else {
        setErrorData({
          title: WRONG_FILE_ERROR_ALERT,
          list: [UPLOAD_ALERT_LIST],
        });
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

  const onPaneClick = useCallback(() => {
    setFilterEdge([]);
  }, []);

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
            onSelectionDragStart={onSelectionDragStart}
            onSelectionEnd={onSelectionEnd}
            onSelectionStart={onSelectionStart}
            connectionRadius={25}
            edgeTypes={{ default: DefaultEdge }}
            connectionLineComponent={ConnectionLineComponent}
            onDragOver={onDragOver}
            onNodeDragStop={onNodeDragStop}
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
              <Controls className="fill-foreground stroke-foreground text-primary [&>button]:border-b-border [&>button]:bg-muted hover:[&>button]:bg-border">
                <ControlButton
                  data-testid="add_note"
                  onClick={() => {
                    const wrapper = reactFlowWrapper.current!;
                    const viewport = reactFlowInstance?.getViewport();
                    const x = wrapper.getBoundingClientRect().width / 2;
                    const y = wrapper.getBoundingClientRect().height / 2;
                    const nodePosition =
                      reactFlowInstance?.screenToFlowPosition({ x, y })!;

                    const data = {
                      node: {
                        description: "",
                        display_name: "",
                        documentation: "",
                        template: {},
                      },
                      type: "note",
                    };
                    const newId = getNodeId(data.type);

                    const newNode: NodeType = {
                      id: newId,
                      type: "noteNode",
                      position: { x: 0, y: 0 },
                      data: {
                        ...data,
                        id: newId,
                      },
                    };
                    paste(
                      { nodes: [newNode], edges: [] },
                      {
                        x: nodePosition.x,
                        y: nodePosition?.y,
                        paneX: wrapper.getBoundingClientRect().x,
                        paneY: wrapper.getBoundingClientRect().y,
                      },
                    );
                  }}
                  className="postion absolute -top-10 rounded-sm"
                >
                  <ShadTooltip content="Add note">
                    <div>
                      <IconComponent
                        name="SquarePen"
                        aria-hidden="true"
                        className="scale-125"
                      />
                    </div>
                  </ShadTooltip>
                </ControlButton>
              </Controls>
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
        <div className="flex h-full w-full items-center justify-center">
          <LoadingComponent remSize={30} />
        </div>
      )}
    </div>
  );
}
