import { useContext, useEffect, useState } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import ConnectionLineComponent from "./components/ConnectionLineComponent";
import { FlowType } from "../../types/flow";
import {
    generateFlow,
    generateNodeFromFlow, validateSelection
} from "../../utils";
import useUndoRedo from "./hooks/useUndoRedo";
import SelectionMenu from "./components/SelectionMenuComponent";
import GroupNode from "../../CustomNodes/GroupNode";

const nodeTypes = {
  genericNode: GenericNode,
  groupNode: GroupNode,
};

export default function FlowPage({ flow }: { flow: FlowType }) {
  let {
    updateFlow,
    disableCopyPaste,
    addFlow,
    getNodeId,
    paste,
    lastCopiedSelection,
    setLastCopiedSelection,
  } = useContext(TabsContext);
  const { types, reactFlowInstance, setReactFlowInstance, templates } =
    useContext(typesContext);
  const reactFlowWrapper = useRef(null);

  const { takeSnapshot } = useUndoRedo();

  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [lastSelection, setLastSelection] =
    useState<OnSelectionChangeParams>(null);

export default function FlowPage() {
  const { flows, tabId, setTabId } = useContext(TabsContext);
  const { id } = useParams();
  useEffect(() => {
    setTabId(id);
  }, [id]);

    const onKeyDown = (event: KeyboardEvent) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key === "c" &&
        lastSelection &&
        !disableCopyPaste
      ) {
        event.preventDefault();
        // console.log(_.cloneDeep(lastSelection));
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
    getVersion().then((data) => {
      setVersion(data.version);
    });
  }, []);

  return (
    <div className="h-full w-full" ref={reactFlowWrapper}>
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
            <Controls className="[&>button]:text-black  [&>button]:dark:border-gray-600 [&>button]:dark:bg-gray-800 [&>button]:dark:fill-gray-400 [&>button]:dark:text-gray-400 hover:[&>button]:dark:bg-gray-700"></Controls>
          </ReactFlow>
          <Chat flow={flow} reactFlowInstance={reactFlowInstance} />
          <SelectionMenu
            onClick={() => {
              if (validateSelection(lastSelection).length === 0) {
                const { newFlow } = generateFlow(
                  lastSelection,
                  reactFlowInstance,
                  "new component"
                );
                const newGroupNode = generateNodeFromFlow(newFlow);
                setNodes((oldNodes) => [
                  ...oldNodes.filter(
                    (oldNode) =>
                      !lastSelection.nodes.some(
                        (selectionNode) => selectionNode.id === oldNode.id
                      )
                  ),
                  newGroupNode,
                ]);
                setEdges((oldEdges) =>
                  oldEdges.filter(
                    (oldEdge) =>
                      !lastSelection.nodes.some(
                        (selectionNode) =>
                          selectionNode.id === oldEdge.target ||
                          selectionNode.id === oldEdge.source
                      )
                  )
                );
              } else {
                setErrorData({
                  title: "Invalid selection",
                  list: validateSelection(lastSelection),
                });
              }
            }}
            isVisible={selectionMenuVisible}
            nodes={lastSelection?.nodes}
          />
        </>
      ) : (
        <></>
      )}
    </div>
  );
}
