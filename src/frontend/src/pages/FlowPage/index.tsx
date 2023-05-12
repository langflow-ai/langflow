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
	NodeDragHandler,
	OnEdgesDelete,
	OnNodesDelete,
	SelectionDragHandler,
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
import useUndoRedo from "./hooks/useUndoRedo";

const nodeTypes = {
	genericNode: GenericNode,
};

var _ = require("lodash");

export default function FlowPage({ flow }: { flow: FlowType }) {
	let { updateFlow, incrementNodeId, disableCP} =
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
	}

	const [lastSelection, setLastSelection] = useState(null);
	const [lastCopiedSelection, setLastCopiedSelection] = useState(null);

	const [position, setPosition] = useState({ x: 0, y: 0 });

	const handleMouseMove = (event) => {
		setPosition({ x: event.clientX, y: event.clientY });
	};

	useOnSelectionChange({
		onChange: (flow) => { setLastSelection(flow); },
	})

	let paste = () => {
		let minimumX = Infinity;
		let minimumY = Infinity;
		let idsMap = {};
		lastCopiedSelection.nodes.forEach((n) => {
			if (n.position.y < minimumY) {
				minimumY = n.position.y
			}
			if (n.position.x < minimumX) {
				minimumX = n.position.x;
			}
		});

		const bounds = reactFlowWrapper.current.getBoundingClientRect();
		const insidePosition = reactFlowInstance.project({
			x: position.x - bounds.left,
			y: position.y - bounds.top
		});

		lastCopiedSelection.nodes.forEach((n) => {

			// Generate a unique node ID
			let newId = getId();
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
			setNodes((nds) => nds.map((e) => ({ ...e, selected: false })).concat({ ...newNode, selected: false }));
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
				addEdge({ source, target, sourceHandle, targetHandle, id, className: "animate-pulse", selected: false }, eds.map((e) => ({ ...e, selected: false })))
			);
		})
	}


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
			takeSnapshot();
			setEdges((eds) =>
				addEdge({ ...params, className: "animate-pulse" }, eds)
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
		[incrementNodeId, reactFlowInstance, setErrorData, setNodes, takeSnapshot]
	);

	const onDelete = useCallback((mynodes) => {
		takeSnapshot();
		setEdges(
			edges.filter(
				(ns) => !mynodes.some((n) => ns.source === n.id || ns.target === n.id)
			)
		);
	}, [takeSnapshot, edges, setEdges]);

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
		<div className="w-full h-full" onMouseMove={handleMouseMove} ref={reactFlowWrapper}>
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
						onEdgesDelete={onEdgesDelete}
						connectionLineComponent={ConnectionLineComponent}
						onDragOver={onDragOver}
						onDrop={onDrop}
						onNodesDelete={onDelete}
						selectNodesOnDrag={false}
					>
						<Background className="dark:bg-gray-900" />
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
