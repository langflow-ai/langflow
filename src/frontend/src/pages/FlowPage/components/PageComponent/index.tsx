import { DefaultEdge } from "@/CustomEdges";
import NoteNode from "@/CustomNodes/NoteNode";
import FlowToolbar from "@/components/core/flowToolbarComponent";
import {
  COLOR_OPTIONS,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { useGetBuildsQuery } from "@/controllers/API/queries/_builds";
import CustomLoader from "@/customization/components/custom-loader";
import { track } from "@/customization/utils/analytics";
import useAutoSaveFlow from "@/hooks/flows/use-autosave-flow";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import { nodeColorsName } from "@/utils/styleUtils";
import { cn, isSupportedNodeTypes } from "@/utils/utils";
import {
  Connection,
  Edge,
  OnNodeDrag,
  OnSelectionChangeParams,
  ReactFlow,
  reconnectEdge,
  SelectionDragHandler,
  OnConnectStartParams,
  OnConnectEnd,
  useReactFlow,
} from "@xyflow/react";
import { AnimatePresence } from "framer-motion";
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
import { useShallow } from "zustand/react/shallow";
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
import { AllNodeType, EdgeType, NoteNodeType } from "../../../../types/flow";
import {
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
import UpdateAllComponents from "../UpdateAllComponents";
import FlowBuildingComponent from "../flowBuildingComponent";
import {
  MemoizedBackground,
  MemoizedCanvasControls,
  MemoizedLogCanvasControls,
  MemoizedSidebarTrigger,
} from "./MemoizedComponents";
import getRandomName from "./utils/get-random-name";
import isWrappedWithClass from "./utils/is-wrapped-with-class";

const nodeTypes = {
  genericNode: GenericNode,
  noteNode: NoteNode,
};

const edgeTypes = {
  default: DefaultEdge,
};

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
  const updateCurrentFlow = useFlowStore((state) => state.updateCurrentFlow);
  const [selectionMenuVisible, setSelectionMenuVisible] = useState(false);
  const edgeUpdateSuccessful = useRef(true);

  const isLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );

  const position = useRef({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams | null>(null);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  useEffect(() => {
    if (currentFlowId !== "") {
      isEmptyFlow.current = nodes.length === 0;
    }
  }, [currentFlowId]);

  const [isAddingNote, setIsAddingNote] = useState(false);
  const [connectStartNode, setConnectStartNode] = useState<string | null>(null);
  const [connectStartHandle, setConnectStartHandle] = useState<string | null>(null);
  const [connectStartHandleType, setConnectStartHandleType] = useState<'source' | 'target' | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  const addComponent = useAddComponent();
  const { screenToFlowPosition, getNode } = useReactFlow();

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

  const undoAction = useShortcutsStore((state) => state.undo);
  const redoAction = useShortcutsStore((state) => state.redo);
  const redoAltAction = useShortcutsStore((state) => state.redoAlt);
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
  useHotkeys("delete", handleDelete);

  // Proximity connect utility functions
  const MIN_PROXIMITY_DISTANCE = 200; // Increased for easier testing

  const getActualHandlePosition = useCallback((nodeId: string, handleId: string): { x: number; y: number } | null => {
    if (!reactFlowWrapper.current) return null;
    
    // Try different handle selectors to find the actual handle element
    const selectors = [
      `[data-id="${nodeId}"] [data-handleid="${handleId}"]`,
      `[data-id="${nodeId}"] [data-id*="${handleId}"]`,
      `.react-flow__node[data-id="${nodeId}"] .react-flow__handle[data-handleid="${handleId}"]`,
      `.react-flow__node[data-id="${nodeId}"] .react-flow__handle[data-id*="${handleId}"]`
    ];
    
    for (const selector of selectors) {
      const handleElement = document.querySelector(selector) as HTMLElement;
      if (handleElement) {
        const handleRect = handleElement.getBoundingClientRect();
        const flowRect = reactFlowWrapper.current.getBoundingClientRect();
        
        // Return screen coordinates instead of flow coordinates
        const position = {
          x: handleRect.left + handleRect.width / 2,
          y: handleRect.top + handleRect.height / 2
        };
        
        return position;
      }
    }
    
    return null;
  }, []);

  const findNearestCompatibleHandle = useCallback((
    endPosition: { x: number; y: number },
    startNodeId: string,
    startHandleId: string,
    startHandleType: 'source' | 'target'
  ): { nodeId: string; handleId: string; handleType: string; position: { x: number; y: number }; distance: number } | null => {
    if (!reactFlowInstance) return null;
    
    console.log('🔍 Searching for compatible handles. Start:', startNodeId, 'Type:', startHandleType);
    console.log('🔍 End position:', endPosition);
    console.log('🔍 Available nodes:', nodes.length);
    
    let nearestHandle: { nodeId: string; handleId: string; handleType: string; position: { x: number; y: number }; distance: number } | null = null;
    let minDistance = MIN_PROXIMITY_DISTANCE;
    
    nodes.forEach(node => {
      if (node.id === startNodeId) {
        console.log('🔍 Skipping start node:', node.id);
        return; // Skip the starting node
      }
      
      console.log('🔍 Checking node:', node.id, 'Data:', node.data);
      
      // Get node position and dimensions
      const nodeRect = reactFlowInstance.getNode(node.id);
      if (!nodeRect) {
        console.log('🔍 No node rect for:', node.id);
        return;
      }
      
      console.log('🔍 Node rect:', nodeRect);
      
      // Check compatible handles based on the start handle type
      const targetHandleType = startHandleType === 'source' ? 'target' : 'source';
      const handleKey = targetHandleType === 'target' ? 'inputs' : 'outputs';
      
      console.log('🔍 Looking for', targetHandleType, 'handles in', handleKey);
      console.log('🔍 Node data[handleKey]:', node.data?.[handleKey]);
      
      if (node.data && node.data[handleKey]) {
        Object.entries(node.data[handleKey]).forEach(([fieldName, handleData]: [string, any]) => {
          console.log('🔍 Processing handle:', fieldName, 'Data:', handleData);
          
          // Generate the actual handle ID used by React Flow
          const handleId = JSON.stringify({
            dataType: handleData.type || 'str',
            id: fieldName,
            name: fieldName,
            output_types: handleData.output_types || [],
          });
          
          console.log('🔍 Generated handle ID:', handleId);
          
          // Get actual handle position from DOM
          let handlePosition = getActualHandlePosition(node.id, handleId);
          
          console.log('🔍 Actual handle position from DOM:', handlePosition);
          console.log('🔍 Expected input handle around screen position:', { x: 993, y: 357 });
          
          if (!handlePosition) {
            // Fallback to estimated position if DOM query fails
            const isInput = targetHandleType === 'target';
            
            // Convert node position to screen coordinates
            const flowPosition = {
              x: nodeRect.position.x + (isInput ? 0 : (nodeRect.width || 200)),
              y: nodeRect.position.y + (nodeRect.height || 100) / 2
            };
            
            // Convert to screen coordinates using React Flow's built-in conversion
            const screenPos = reactFlowInstance.flowToScreenPosition(flowPosition);
            
            handlePosition = {
              x: screenPos.x,
              y: screenPos.y
            };
            console.log('🔍 Using fallback position:', handlePosition);
          }
          
          // Calculate distance
          const distance = Math.sqrt(
            Math.pow(endPosition.x - handlePosition.x, 2) + 
            Math.pow(endPosition.y - handlePosition.y, 2)
          );
          
          console.log('🔍 Distance to handle:', distance, 'Min distance:', minDistance);
          console.log('🔍 Handle position:', handlePosition, 'End position:', endPosition);
          
          if (distance < minDistance) {
            console.log('🔍 Handle is within range! Testing connection validity...');
            // Check if connection would be valid
            const testConnection: Connection = {
              source: startHandleType === 'source' ? startNodeId : node.id,
              target: startHandleType === 'source' ? node.id : startNodeId,
              sourceHandle: startHandleType === 'source' ? startHandleId : handleId,
              targetHandle: startHandleType === 'source' ? handleId : startHandleId
            };
            
            // Check if connection would be valid (includes type compatibility and edge validation)
            if (isValidConnection(testConnection, nodes, edges)) {
              minDistance = distance;
              nearestHandle = {
                nodeId: node.id,
                handleId: handleId,
                handleType: targetHandleType,
                position: handlePosition,
                distance: distance
              };
            }
          }
        });
      }
    });
    
    return nearestHandle;
  }, [nodes, edges, reactFlowInstance, getActualHandlePosition]);

  const onConnectMod = useCallback(
    (params: Connection) => {
      takeSnapshot();
      onConnect(params);
      track("New Component Connection Added");
    },
    [takeSnapshot, onConnect],
  );

  const onConnectStart = useCallback((event: any, params: OnConnectStartParams) => {
    console.log('🔵 Proximity connect - connection started:', params);
    setIsConnecting(true);
    setConnectStartNode(params.nodeId || null);
    setConnectStartHandle(params.handleId || null);
    setConnectStartHandleType(params.handleType || null);

    let isConnectionMade = false;
    let intervalId: NodeJS.Timeout;

    // Periodic proximity checking since mouse events might not fire properly
    const checkProximity = () => {
      console.log('🔶 checkProximity called - isConnectionMade:', isConnectionMade, 'reactFlowWrapper:', !!reactFlowWrapper.current);
      
      if (isConnectionMade) {
        console.log('🔶 Connection already made, skipping');
        return;
      }
      
      if (!reactFlowWrapper.current) {
        console.log('🔶 No reactFlowWrapper, skipping');
        return;
      }
      
      // Get current mouse position from the global position tracker
      const currentMousePosition = position.current;
      console.log('🔶 Checking proximity at position:', currentMousePosition);

      // Find nearest compatible handle
      const nearestHandle = findNearestCompatibleHandle(
        currentMousePosition,
        params.nodeId || null,
        params.handleId || null,
        params.handleType || null
      );

      console.log('🔶 Found nearest handle:', nearestHandle);

      if (nearestHandle && nearestHandle.distance <= 150) {
        console.log('🟢 Auto-connecting - handles are within proximity!', nearestHandle);
        
        // Create the connection automatically
        const connection: Connection = {
          source: params.handleType === 'source' ? params.nodeId! : nearestHandle.nodeId,
          target: params.handleType === 'source' ? nearestHandle.nodeId : params.nodeId!,
          sourceHandle: params.handleType === 'source' ? params.handleId! : nearestHandle.handleId,
          targetHandle: params.handleType === 'source' ? nearestHandle.handleId : params.handleId!
        };

        console.log('🟢 Creating auto-connection:', connection);
        onConnectMod(connection);
        isConnectionMade = true;
        
        // Clean up immediately after connection
        cleanup();
      }
    };

    const handleMouseUp = () => {
      console.log('🔶 Mouse up - final proximity check');
      checkProximity(); // Final check on mouse up
      cleanup();
    };

    const cleanup = () => {
      if (intervalId) clearInterval(intervalId);
      document.removeEventListener('mouseup', handleMouseUp);
      setIsConnecting(false);
      setConnectStartNode(null);
      setConnectStartHandle(null);
      setConnectStartHandleType(null);
    };

    console.log('🔶 Setting up proximity checking for connection');
    // Check proximity periodically during drag
    intervalId = setInterval(checkProximity, 50); // Check every 50ms
    document.addEventListener('mouseup', handleMouseUp);
    
    // Also do an immediate check
    setTimeout(checkProximity, 100);
  }, [findNearestCompatibleHandle, onConnectMod]);

  const onConnectEnd: OnConnectEnd = useCallback((event) => {
    console.log('🔴 onConnectEnd called with event:', event);
    console.log('🔴 Connection state:', { connectStartNode, connectStartHandle, connectStartHandleType, reactFlowInstance: !!reactFlowInstance });
    
    if (!connectStartNode || !connectStartHandle || !connectStartHandleType || !reactFlowInstance) {
      console.log('🔴 onConnectEnd: Missing required state, exiting');
      setIsConnecting(false);
      setConnectStartNode(null);
      setConnectStartHandle(null);
      setConnectStartHandleType(null);
      return;
    }

    // Get the end position from the mouse event
    const rect = reactFlowWrapper.current?.getBoundingClientRect();
    if (!rect) {
      setIsConnecting(false);
      setConnectStartNode(null);
      setConnectStartHandle(null);
      setConnectStartHandleType(null);
      return;
    }
    
    let clientX: number, clientY: number;
    
    if (event instanceof MouseEvent) {
      clientX = event.clientX;
      clientY = event.clientY;
    } else if (event instanceof TouchEvent && event.touches.length > 0) {
      clientX = event.touches[0].clientX;
      clientY = event.touches[0].clientY;
    } else {
      setIsConnecting(false);
      setConnectStartNode(null);
      setConnectStartHandle(null);
      setConnectStartHandleType(null);
      return;
    }
    
    const screenPosition = { x: clientX, y: clientY };
    console.log('🟡 Proximity connect - looking for nearest handle from screen position:', screenPosition);

    // Find nearest compatible handle using screen coordinates
    const nearestHandle = findNearestCompatibleHandle(
      screenPosition,
      connectStartNode,
      connectStartHandle,
      connectStartHandleType
    );

    console.log('🟡 Proximity connect - found nearest handle:', nearestHandle);

    if (nearestHandle && nearestHandle.distance <= 150) {
      console.log('🟢 Creating proximity connection! Distance:', nearestHandle.distance);
      
      // Create the connection
      const connection: Connection = {
        source: connectStartHandleType === 'source' ? connectStartNode : nearestHandle.nodeId,
        target: connectStartHandleType === 'source' ? nearestHandle.nodeId : connectStartNode,
        sourceHandle: connectStartHandleType === 'source' ? connectStartHandle : nearestHandle.handleId,
        targetHandle: connectStartHandleType === 'source' ? nearestHandle.handleId : connectStartHandle
      };

      console.log('🟢 Connection details:', connection);
      onConnectMod(connection);
    } else {
      console.log('🔴 No proximity connection - distance:', nearestHandle?.distance || 'N/A');
    }

    // Reset state
    setIsConnecting(false);
    setConnectStartNode(null);
    setConnectStartHandle(null);
    setConnectStartHandleType(null);
  }, [connectStartNode, connectStartHandle, connectStartHandleType, reactFlowInstance, screenToFlowPosition, findNearestCompatibleHandle, onConnectMod]);

  // Debug state changes
  useEffect(() => {
    console.log('🔵 Connection state changed:', { isConnecting, connectStartNode, connectStartHandle, connectStartHandleType });
  }, [isConnecting, connectStartNode, connectStartHandle, connectStartHandleType]);


  const onNodeDragStart: OnNodeDrag = useCallback(() => {
    // 👇 make dragging a node undoable

    takeSnapshot();
    // 👉 you can place your event handlers here
  }, [takeSnapshot]);

  const onNodeDragStop: OnNodeDrag = useCallback(() => {
    // 👇 make moving the canvas undoable
    autoSaveFlow();
    updateCurrentFlow({ nodes });
    setPositionDictionary({});
  }, [
    takeSnapshot,
    autoSaveFlow,
    nodes,
    edges,
    reactFlowInstance,
    setPositionDictionary,
  ]);

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
    },
    [],
  );

  const onPaneClick = useCallback(
    (event: React.MouseEvent) => {
      setFilterEdge([]);
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
          data: {
            ...data,
            id: newId,
          },
        };
        setNodes((nds) => nds.concat(newNode));
        setIsAddingNote(false);
      }
    },
    [isAddingNote, setNodes, reactFlowInstance, getNodeId, setFilterEdge],
  );

  const handleEdgeClick = (event, edge) => {
    if (isLocked) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const color =
      nodeColorsName[edge?.data?.sourceHandle?.output_types[0]] || "cyan";

    const accentColor = `hsl(var(--datatype-${color}))`;
    reactFlowWrapper.current?.style.setProperty("--selected", accentColor);
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

  const componentsToUpdate = useFlowStore((state) => state.componentsToUpdate);

  const MIN_ZOOM = 0.2;
  const MAX_ZOOM = 8;
  const fitViewOptions = {
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
  };

  return (
    <div className="h-full w-full bg-canvas" ref={reactFlowWrapper}>
      {showCanvas ? (
        <div id="react-flow-id" className="h-full w-full bg-canvas">
          {!view && (
            <>
              <MemoizedLogCanvasControls />
              <MemoizedCanvasControls
                setIsAddingNote={setIsAddingNote}
                position={position.current}
                shadowBoxWidth={shadowBoxWidth}
                shadowBoxHeight={shadowBoxHeight}
              />
              <FlowToolbar />
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
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={isLocked ? undefined : onConnectMod}
            onConnectStart={isLocked ? undefined : onConnectStart}
            onConnectEnd={isLocked ? undefined : onConnectEnd}
            disableKeyboardA11y={true}
            onInit={setReactFlowInstance}
            nodeTypes={nodeTypes}
            onReconnect={isLocked ? undefined : onEdgeUpdate}
            onReconnectStart={isLocked ? undefined : onEdgeUpdateStart}
            onReconnectEnd={isLocked ? undefined : onEdgeUpdateEnd}
            onNodeDragStart={onNodeDragStart}
            onSelectionDragStart={onSelectionDragStart}
            elevateEdgesOnSelect={true}
            onSelectionEnd={onSelectionEnd}
            onSelectionStart={onSelectionStart}
            connectionRadius={30}
            edgeTypes={edgeTypes}
            connectionLineComponent={ConnectionLineComponent}
            onDragOver={onDragOver}
            onNodeDragStop={onNodeDragStop}
            onDrop={onDrop}
            onSelectionChange={onSelectionChange}
            deleteKeyCode={[]}
            fitView={isEmptyFlow.current ? false : true}
            fitViewOptions={fitViewOptions}
            className="theme-attribution"
            minZoom={MIN_ZOOM}
            maxZoom={MAX_ZOOM}
            zoomOnScroll={!view}
            zoomOnPinch={!view}
            panOnDrag={!view}
            panActivationKeyCode={""}
            proOptions={{ hideAttribution: true }}
            onPaneClick={onPaneClick}
            onEdgeClick={handleEdgeClick}
          >
            <FlowBuildingComponent />
            <UpdateAllComponents />
            <MemoizedBackground />
          </ReactFlow>
          <div
            id="shadow-box"
            style={{
              position: "absolute",
              width: `${shadowBoxWidth}px`,
              height: `${shadowBoxHeight}px`,
              backgroundColor: `${shadowBoxBackgroundColor}`,
              opacity: 0.7,
              pointerEvents: "none",
              // Prevent shadow-box from showing unexpectedly during initial renders
              display: "none",
            }}
          ></div>
        </div>
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <CustomLoader remSize={30} />
        </div>
      )}
    </div>
  );
}
