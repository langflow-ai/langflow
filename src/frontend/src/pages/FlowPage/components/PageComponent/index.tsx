import {
  type Connection,
  type Edge,
  type NodeChange,
  type OnNodeDrag,
  type OnSelectionChangeParams,
  ReactFlow,
  reconnectEdge,
  type SelectionDragHandler,
} from "@xyflow/react";
import _, { cloneDeep } from "lodash";
import {
  type KeyboardEvent,
  type MouseEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import FlowToolbar from "@/components/core/flowToolbarComponent";
import {
  COLOR_OPTIONS,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useGetBuildsQuery } from "@/controllers/API/queries/_builds";
import CustomLoader from "@/customization/components/custom-loader";
import { track } from "@/customization/utils/analytics";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAutoSaveFlow from "@/hooks/flows/use-autosave-flow";
import { useFlowEvents } from "@/hooks/flows/use-flow-events";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import InspectionPanel from "@/pages/FlowPage/components/InspectionPanel";
import { nodeColorsName } from "@/utils/styleUtils";
import { isSupportedNodeTypes } from "@/utils/utils";
import {
  INVALID_SELECTION_ERROR_ALERT,
  UPLOAD_ALERT_LIST,
  UPLOAD_ERROR_ALERT,
  WRONG_FILE_ERROR_ALERT,
} from "../../../../constants/alerts_constants";
import ExportModal from "../../../../modals/exportModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useTypesStore } from "../../../../stores/typesStore";
import useVersionPreviewStore from "../../../../stores/versionPreviewStore";
import type { APIClassType } from "../../../../types/api";
import type {
  AllNodeType,
  EdgeType,
  FlowType,
  NoteNodeType,
} from "../../../../types/flow";
import {
  generateFlow,
  generateNodeFromFlow,
  getNodeId,
  isValidConnection,
  scapeJSONParse,
  updateIds,
  validateSelection,
} from "../../../../utils/reactflowUtils";
import { edgeTypes, nodeTypes } from "../../consts";
import ConnectionLineComponent from "../ConnectionLineComponent";
import FlowBuildingComponent from "../flowBuildingComponent";
import SelectionMenu from "../SelectionMenuComponent";
import UpdateAllComponents from "../UpdateAllComponents";
import { CanvasBadge } from "./components/CanvasBanner";
import HelperLines from "./components/helper-lines";
import VersionPreviewOverlay from "./components/VersionPreviewOverlay";
import {
  getHelperLines,
  getSnapPosition,
  type HelperLinesState,
} from "./helpers/helper-lines";
import {
  MemoizedBackground,
  MemoizedCanvasControls,
  MemoizedSidebarTrigger,
} from "./MemoizedComponents";
import getRandomName from "./utils/get-random-name";
import isWrappedWithClass from "./utils/is-wrapped-with-class";

export default function Page({
  view,
  setIsLoading,
}: {
  view?: boolean;
  setIsLoading: (isLoading: boolean) => void;
}): JSX.Element {
  const uploadFlow = useUploadFlow();
  const autoSaveFlow = useAutoSaveFlow();
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const setFilterComponent = useFlowStore((state) => state.setFilterComponent);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const setPositionDictionary = useFlowStore(
    (state) => state.setPositionDictionary,
  );
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const setReactFlowInstance = useFlowStore(
    (state) => state.setReactFlowInstance,
  );
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const isEmptyFlow = useRef(nodes.length === 0);

  const previewLabel = useVersionPreviewStore((s) => s.previewLabel);
  const isPreviewActive = previewLabel !== null;
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
  const setRightClickedNodeId = useFlowStore(
    (state) => state.setRightClickedNodeId,
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const updateCurrentFlow = useFlowStore((state) => state.updateCurrentFlow);
  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);
  const [openExportModal, setOpenExportModal] = useState(false);
  const edgeUpdateSuccessful = useRef(true);

  const isLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );

  const position = useRef({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const { isAgentWorking, events, lastSettledAt, clearEvents } = useFlowEvents(
    currentFlowId || undefined,
  );
  const effectiveLocked = isLocked || isAgentWorking;

  // Keep banner mounted during exit animation, preserve last text
  const [bannerVisible, setBannerVisible] = useState(false);
  const bannerVisibleRef = useRef(false);
  const [bannerExiting, setBannerExiting] = useState(false);
  const [bannerText, setBannerText] = useState(
    "Agent is working on this flow...",
  );

  // Update banner text while active (not during exit)
  useEffect(() => {
    if (isAgentWorking && events.length > 0) {
      const last = events[events.length - 1];
      if (last.summary) {
        setBannerText(`Agent: ${last.summary}`);
      }
    }
  }, [isAgentWorking, events]);

  useEffect(() => {
    if (isAgentWorking) {
      setBannerExiting(false);
      setBannerVisible(true);
      bannerVisibleRef.current = true;
    } else if (bannerVisibleRef.current) {
      // bannerText is already frozen - don't update it during exit
      setBannerExiting(true);
      const timer = setTimeout(() => {
        setBannerVisible(false);
        bannerVisibleRef.current = false;
        setBannerExiting(false);
        setBannerText("Agent is working on this flow...");
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [isAgentWorking]);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const prevSettledRef = useRef<number | null>(null);

  const eventsRef = useRef(events);
  eventsRef.current = events;

  useEffect(() => {
    if (
      lastSettledAt &&
      lastSettledAt !== prevSettledRef.current &&
      currentFlowId
    ) {
      prevSettledRef.current = lastSettledAt;
      const targetFlowId = currentFlowId;

      // Capture events before clearing
      const settleEvents = [...eventsRef.current];
      clearEvents();

      const controller = new AbortController();

      api
        .get<FlowType>(`${getURL("FLOWS")}/${targetFlowId}`, {
          signal: controller.signal,
        })
        .then((response) => {
          // Verify we're still on the same flow
          if (useFlowsManagerStore.getState().currentFlowId !== targetFlowId) {
            return;
          }

          applyFlowToCanvas(response.data);
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              reactFlowInstance?.fitView({
                padding: { left: "20px", right: "20px", top: "80px" },
              });
            });
          });

          const nonSettleEvents = settleEvents.filter(
            (e) => e.type !== "flow_settled",
          );
          if (nonSettleEvents.length > 0) {
            const counts: Record<string, number> = {};
            for (const e of nonSettleEvents) {
              const key =
                {
                  component_added: "added",
                  component_removed: "removed",
                  component_configured: "configured",
                  connection_added: "connected",
                  connection_removed: "disconnected",
                  flow_updated: "updated",
                }[e.type] || "changed";
              counts[key] = (counts[key] || 0) + 1;
            }
            const parts = Object.entries(counts).map(([action, count]) => {
              const isConnection =
                action === "connected" || action === "disconnected";
              const base = isConnection ? "connection" : "component";
              const noun = count === 1 ? base : `${base}s`;
              return `${action} ${count} ${noun}`;
            });
            setSuccessData({
              title: `Agent ${parts.join(", ")}`,
            });
          }
        })
        .catch((error) => {
          if (error?.name === "CanceledError") return;
          const isNetwork = error?.response || error?.request;
          console.error(
            "[FlowPage] Failed to reload flow after agent changes:",
            error,
          );
          setErrorData({
            title: isNetwork
              ? "Network error reloading flow after agent changes. Try refreshing."
              : "Error applying agent changes to canvas. Try refreshing.",
          });
        });

      return () => controller.abort();
    }
  }, [
    lastSettledAt,
    currentFlowId,
    applyFlowToCanvas,
    setSuccessData,
    setErrorData,
    clearEvents,
  ]);

  useEffect(() => {
    if (currentFlowId !== "") {
      isEmptyFlow.current = nodes.length === 0;
    }
  }, [currentFlowId]);

  const [isAddingNote, setIsAddingNote] = useState(false);

  const addComponent = useAddComponent();

  const zoomLevel = reactFlowInstance?.getZoom();
  const shadowBoxWidth = NOTE_NODE_MIN_WIDTH * (zoomLevel || 1);
  const shadowBoxHeight = NOTE_NODE_MIN_HEIGHT * (zoomLevel || 1);
  const shadowBoxBackgroundColor = COLOR_OPTIONS[Object.keys(COLOR_OPTIONS)[0]];

  const handleGroupNode = useCallback(() => {
    takeSnapshot();
    const edgesState = useFlowStore.getState().edges;
    if (validateSelection(lastSelection!, edgesState).length === 0) {
      const clonedNodes = cloneDeep(useFlowStore.getState().nodes);
      const clonedEdges = cloneDeep(edgesState);
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
        list: validateSelection(lastSelection!, edgesState),
      });
    }
  }, [lastSelection, setNodes, setErrorData, takeSnapshot]);

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
    setIsLoading(!showCanvas);
  }, [showCanvas]);

  useEffect(() => {
    useFlowStore.setState({ autoSaveFlow });
  }, [autoSaveFlow]);

  function handleUndo(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      undo();
    }
  }

  function handleRedo(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      redo();
    }
  }

  function handleGroup(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
    if (selectionMenuVisible) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      handleGroupNode();
    }
  }

  function handleDuplicate(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
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
    const hasTextSelection =
      (window.getSelection()?.toString().length ?? 0) > 0;

    if (
      !isWrappedWithClass(e, "noflow") &&
      !hasTextSelection &&
      (isWrappedWithClass(e, "react-flow__node") || multipleSelection)
    ) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      if (lastSelection) {
        setLastCopiedSelection(_.cloneDeep(lastSelection));
      }
    }
  }

  function handleCut(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      if (window.getSelection()?.toString().length === 0 && lastSelection) {
        setLastCopiedSelection(_.cloneDeep(lastSelection), true);
      }
    }
  }

  function handlePaste(e: KeyboardEvent) {
    if (isPreviewActive || effectiveLocked) return;
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
    if (isPreviewActive) return;
    if (effectiveLocked) return;
    if (!isWrappedWithClass(e, "nodelete") && lastSelection) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      takeSnapshot();
      if (lastSelection.edges?.length) {
        track("Component Connection Deleted");
      }
      if (lastSelection.nodes?.length) {
        lastSelection.nodes.forEach((n) => {
          track("Component Deleted", { componentType: n.data.type });
        });
      }
      deleteNode(lastSelection.nodes.map((node) => node.id));
      deleteEdge(lastSelection.edges.map((edge) => edge.id));
    }
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === "Escape") {
      setRightClickedNodeId(null);
    }
  }

  function handleDownload(e: KeyboardEvent) {
    if (!isWrappedWithClass(e, "noflow")) {
      e.preventDefault();
      (e as unknown as Event).stopImmediatePropagation();
      setOpenExportModal(true);
    }
  }

  const undoAction = useShortcutsStore((state) => state.undo);
  const redoAction = useShortcutsStore((state) => state.redo);
  const redoAltAction = useShortcutsStore((state) => state.redoAlt);
  const copyAction = useShortcutsStore((state) => state.copy);
  const duplicate = useShortcutsStore((state) => state.duplicate);
  const deleteAction = useShortcutsStore((state) => state.delete);
  const groupAction = useShortcutsStore((state) => state.group);
  const cutAction = useShortcutsStore((state) => state.cut);
  const pasteAction = useShortcutsStore((state) => state.paste);
  const downloadAction = useShortcutsStore((state) => state.download);
  //@ts-ignore
  useHotkeys(undoAction, handleUndo);
  //@ts-ignore
  useHotkeys(redoAction, handleRedo);
  //@ts-ignore
  useHotkeys(redoAltAction, handleRedo);
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
  useHotkeys(downloadAction, handleDownload);
  //@ts-ignore
  useHotkeys("delete", handleDelete);
  //@ts-ignore
  useHotkeys("escape", handleEscape);

  const onConnectMod = useCallback(
    (params: Connection) => {
      takeSnapshot();
      onConnect(params);
      track("New Component Connection Added");
    },
    [takeSnapshot, onConnect],
  );

  const [helperLines, setHelperLines] = useState<HelperLinesState>({});
  const [isDragging, setIsDragging] = useState(false);
  const helperLineEnabled = useFlowStore((state) => state.helperLineEnabled);

  const onNodeDrag: OnNodeDrag = useCallback(
    (_, node) => {
      if (helperLineEnabled) {
        const currentHelperLines = getHelperLines(node, nodes);
        setHelperLines(currentHelperLines);
      }
    },
    [helperLineEnabled, nodes],
  );

  const onNodeDragStart: OnNodeDrag = useCallback(
    (_, node) => {
      // 👇 make dragging a node undoable
      takeSnapshot();
      setIsDragging(true);
      // 👉 you can place your event handlers here
    },
    [takeSnapshot],
  );

  const onNodeDragStop: OnNodeDrag = useCallback(
    (_, node) => {
      // 👇 make moving the canvas undoable
      autoSaveFlow();
      updateCurrentFlow({ nodes });
      setPositionDictionary({});
      setIsDragging(false);
      setHelperLines({});
    },
    [
      takeSnapshot,
      autoSaveFlow,
      nodes,
      edges,
      reactFlowInstance,
      setPositionDictionary,
    ],
  );

  const onNodesChangeWithHelperLines = useCallback(
    (changes: NodeChange<AllNodeType>[]) => {
      if (!helperLineEnabled) {
        onNodesChange(changes);
        return;
      }

      // Apply snapping to position changes during drag
      const modifiedChanges = changes.map((change) => {
        if (
          change.type === "position" &&
          "dragging" in change &&
          "position" in change &&
          "id" in change &&
          isDragging
        ) {
          const nodeId = change.id as string;
          const draggedNode = nodes.find((n) => n.id === nodeId);

          if (draggedNode && change.position) {
            const updatedNode = {
              ...draggedNode,
              position: change.position,
            };

            const snapPosition = getSnapPosition(updatedNode, nodes);

            // Only snap if we're actively dragging
            if (change.dragging) {
              // Apply snap if there's a significant difference
              if (
                Math.abs(snapPosition.x - change.position.x) > 0.1 ||
                Math.abs(snapPosition.y - change.position.y) > 0.1
              ) {
                return {
                  ...change,
                  position: snapPosition,
                };
              }
            } else {
              // This is the final position change when drag ends
              // Force snap to ensure it stays where it should
              return {
                ...change,
                position: snapPosition,
              };
            }
          }
        }
        return change;
      });

      onNodesChange(modifiedChanges);
    },
    [onNodesChange, nodes, isDragging, helperLineEnabled],
  );

  const onSelectionDragStart: SelectionDragHandler = useCallback(() => {
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
      if (effectiveLocked) return;
      const grabbingElement =
        document.getElementsByClassName("cursor-grabbing");
      if (grabbingElement.length > 0) {
        document.body.removeChild(grabbingElement[0]);
      }
      if (event.dataTransfer.types.some((type) => isSupportedNodeTypes(type))) {
        takeSnapshot();

        const datakey = event.dataTransfer.types.find((type) =>
          isSupportedNodeTypes(type),
        );

        // Extract the data from the drag event and parse it as a JSON object
        const data: { type: string; node?: APIClassType } = JSON.parse(
          event.dataTransfer.getData(datakey!),
        );

        addComponent(data.node!, data.type, {
          x: event.clientX,
          y: event.clientY,
        });
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
    [takeSnapshot, addComponent],
  );

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: EdgeType, newConnection: Connection) => {
      if (isValidConnection(newConnection, nodes, edges)) {
        edgeUpdateSuccessful.current = true;
        oldEdge.data = {
          targetHandle: scapeJSONParse(newConnection.targetHandle!),
          sourceHandle: scapeJSONParse(newConnection.sourceHandle!),
        };
        setEdges((els) => reconnectEdge(oldEdge, newConnection, els));
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
      if (flow.nodes && (flow.nodes.length === 0 || flow.nodes.length > 1)) {
        setRightClickedNodeId(null);
      }
    },
    [setRightClickedNodeId],
  );

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: AllNodeType) => {
      event.preventDefault();
      if (effectiveLocked) return;

      // Set the right-clicked node ID to show its dropdown menu
      setRightClickedNodeId(node.id);

      // Focus/select the right-clicked node (same as left-click behavior)
      setNodes((currentNodes) => {
        return currentNodes.map((n) => ({
          ...n,
          selected: n.id === node.id,
        }));
      });
    },
    [effectiveLocked, setRightClickedNodeId, setNodes],
  );

  const onPaneClick = useCallback(
    (event: React.MouseEvent) => {
      setFilterEdge([]);
      setFilterComponent("");
      // Hide right-click dropdown when clicking on the pane
      setRightClickedNodeId(null);
      if (isAddingNote) {
        const shadowBox = document.getElementById("shadow-box");
        if (shadowBox) {
          shadowBox.style.display = "none";
        }
        const position = reactFlowInstance?.screenToFlowPosition({
          x: event.clientX - shadowBoxWidth / 2,
          y: event.clientY - shadowBoxHeight / 2,
        });
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

        const newNode: NoteNodeType = {
          id: newId,
          type: "noteNode",
          position: position || { x: 0, y: 0 },
          width: NOTE_NODE_MIN_WIDTH,
          height: NOTE_NODE_MIN_HEIGHT,
          data: {
            ...data,
            id: newId,
          },
        };
        setNodes((nds) => nds.concat(newNode));
        setIsAddingNote(false);
        // Signal sidebar to revert add_note active state
        window.dispatchEvent(new Event("lf:end-add-note"));
      }
    },
    [
      isAddingNote,
      setNodes,
      reactFlowInstance,
      getNodeId,
      setFilterEdge,
      setFilterComponent,
    ],
  );

  const handleEdgeClick = (event, edge) => {
    if (effectiveLocked) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const color =
      nodeColorsName[edge?.data?.sourceHandle?.output_types[0]] || "cyan";

    const accentColor = `hsl(var(--datatype-${color}))`;
    reactFlowWrapper.current?.style.setProperty("--selected", accentColor);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (effectiveLocked) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  useEffect(() => {
    const handleGlobalMouseMove = (event) => {
      if (isAddingNote) {
        const shadowBox = document.getElementById("shadow-box");
        if (shadowBox) {
          shadowBox.style.display = "block";
          shadowBox.style.left = `${event.clientX - shadowBoxWidth / 2}px`;
          shadowBox.style.top = `${event.clientY - shadowBoxHeight / 2}px`;
        }
      }
    };

    document.addEventListener("mousemove", handleGlobalMouseMove);

    return () => {
      document.removeEventListener("mousemove", handleGlobalMouseMove);
    };
  }, [isAddingNote, shadowBoxWidth, shadowBoxHeight]);

  // Listen for a global event to start the add-note flow from outside components
  useEffect(() => {
    const handleStartAddNote = () => {
      setIsAddingNote(true);
      const shadowBox = document.getElementById("shadow-box");
      if (shadowBox) {
        shadowBox.style.display = "block";
        shadowBox.style.left = `${position.current.x - shadowBoxWidth / 2}px`;
        shadowBox.style.top = `${position.current.y - shadowBoxHeight / 2}px`;
      }
    };

    window.addEventListener("lf:start-add-note", handleStartAddNote);
    return () => {
      window.removeEventListener("lf:start-add-note", handleStartAddNote);
    };
  }, [shadowBoxWidth, shadowBoxHeight]);

  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 2;
  const fitViewOptions = {
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
  };

  // Get inspection panel visibility from store
  const inspectionPanelVisible = useFlowStore(
    (state) => state.inspectionPanelVisible,
  );

  // Determine if a single generic node is selected
  const hasSingleGenericNodeSelected =
    lastSelection?.nodes?.length === 1 &&
    lastSelection.nodes[0].type === "genericNode";

  // Get the fresh node data from the store instead of using stale reference
  const selectedNodeId = hasSingleGenericNodeSelected
    ? lastSelection.nodes[0].id
    : null;
  const selectedNode = selectedNodeId
    ? (nodes.find((n) => n.id === selectedNodeId) as AllNodeType)
    : null;

  // Determine if InspectionPanel should be visible
  const showInspectionPanel = inspectionPanelVisible && !!selectedNode;

  // Handler to close the inspection panel by deselecting all nodes
  const handleCloseInspectionPanel = useCallback(() => {
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        selected: false,
      })),
    );
  }, [setNodes]);

  useEffect(() => {
    if (inspectionPanelVisible) {
      setSelectionMenuVisible(false);
    }
  }, [inspectionPanelVisible]);

  return (
    <div className="h-full w-full bg-canvas" ref={reactFlowWrapper}>
      {showCanvas ? (
        <>
          <div id="react-flow-id" className="h-full w-full bg-canvas relative">
            {!view && (
              <>
                <MemoizedCanvasControls
                  selectedNode={selectedNode}
                  setIsAddingNote={setIsAddingNote}
                  shadowBoxWidth={shadowBoxWidth}
                  shadowBoxHeight={shadowBoxHeight}
                  isAgentWorking={isAgentWorking}
                />
                {!isPreviewActive && <FlowToolbar />}
                {inspectionPanelVisible && (
                  <InspectionPanel selectedNode={selectedNode} />
                )}
              </>
            )}
            <MemoizedSidebarTrigger />
            <SelectionMenu
              lastSelection={lastSelection}
              isVisible={selectionMenuVisible}
              nodes={lastSelection?.nodes}
              onClick={handleGroupNode}
            />
            <ReactFlow<AllNodeType, EdgeType>
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChangeWithHelperLines}
              onEdgesChange={onEdgesChange}
              onConnect={
                effectiveLocked || isPreviewActive ? undefined : onConnectMod
              }
              disableKeyboardA11y={true}
              nodesFocusable={!effectiveLocked && !isPreviewActive}
              edgesFocusable={!effectiveLocked && !isPreviewActive}
              nodesDraggable={!isPreviewActive && !effectiveLocked}
              nodesConnectable={!isPreviewActive && !effectiveLocked}
              elementsSelectable={!isPreviewActive && !effectiveLocked}
              onInit={setReactFlowInstance}
              nodeTypes={nodeTypes}
              onReconnect={
                effectiveLocked || isPreviewActive ? undefined : onEdgeUpdate
              }
              onReconnectStart={
                effectiveLocked || isPreviewActive
                  ? undefined
                  : onEdgeUpdateStart
              }
              onReconnectEnd={
                effectiveLocked || isPreviewActive ? undefined : onEdgeUpdateEnd
              }
              onNodeDrag={isPreviewActive ? undefined : onNodeDrag}
              onNodeDragStart={isPreviewActive ? undefined : onNodeDragStart}
              onSelectionDragStart={
                isPreviewActive ? undefined : onSelectionDragStart
              }
              elevateEdgesOnSelect={false}
              onSelectionEnd={isPreviewActive ? undefined : onSelectionEnd}
              onSelectionStart={isPreviewActive ? undefined : onSelectionStart}
              connectionRadius={30}
              edgeTypes={edgeTypes}
              connectionLineComponent={ConnectionLineComponent}
              onDragOver={isPreviewActive ? undefined : onDragOver}
              onNodeDragStop={isPreviewActive ? undefined : onNodeDragStop}
              onDrop={isPreviewActive ? undefined : onDrop}
              onSelectionChange={onSelectionChange}
              deleteKeyCode={[]}
              fitView={isEmptyFlow.current ? false : true}
              fitViewOptions={fitViewOptions}
              className="theme-attribution"
              tabIndex={effectiveLocked ? -1 : undefined}
              minZoom={MIN_ZOOM}
              maxZoom={MAX_ZOOM}
              zoomOnScroll={!view}
              zoomOnPinch={!view}
              selectNodesOnDrag={false}
              panOnDrag={!view}
              panActivationKeyCode={""}
              proOptions={{ hideAttribution: true }}
              onPaneClick={onPaneClick}
              onEdgeClick={handleEdgeClick}
              onKeyDown={handleKeyDown}
              onNodeContextMenu={onNodeContextMenu}
            >
              <UpdateAllComponents />
              <MemoizedBackground />
              {helperLineEnabled && <HelperLines helperLines={helperLines} />}
            </ReactFlow>
            <FlowBuildingComponent />
            {bannerVisible && (
              <div
                className={`pointer-events-none absolute inset-0 z-50 ${bannerExiting ? "agent-badge-exit" : "agent-badge-enter"}`}
              >
                <CanvasBadge>
                  <ForwardedIconComponent
                    name="Loader2"
                    className="h-4 w-4 animate-spin"
                  />
                  <span
                    key={bannerExiting ? "exit" : bannerText}
                    className={
                      bannerExiting ? "text-sm" : "agent-text-enter text-sm"
                    }
                  >
                    {bannerText}
                  </span>
                </CanvasBadge>
              </div>
            )}
            {isPreviewActive && <VersionPreviewOverlay />}
          </div>
          <div
            id="shadow-box"
            style={{
              position: "absolute",
              width: `${shadowBoxWidth}px`,
              height: `${shadowBoxHeight}px`,
              backgroundColor: `${shadowBoxBackgroundColor}`,
              opacity: 0.7,
              pointerEvents: "none",
              borderRadius: "12px",
              // Prevent shadow-box from showing unexpectedly during initial renders
              display: "none",
            }}
          ></div>
        </>
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <CustomLoader remSize={30} />
        </div>
      )}
      <ExportModal open={openExportModal} setOpen={setOpenExportModal} />
    </div>
  );
}
