import { useCallback, useContext, useEffect, useRef } from "react";
import ReactFlow, {
	Background,
	Controls,
	addEdge,
	useEdgesState,
	useNodesState,
	useReactFlow,
	ControlButton,
	EdgeChange,
	Connection,
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

const nodeTypes = {
	genericNode: GenericNode,
};

var _ = require("lodash");

export default function FlowPage({ flow }:{flow:FlowType}) {
	let { updateFlow, incrementNodeId, downloadFlow, uploadFlow } =
		useContext(TabsContext);
	const { types, reactFlowInstance, setReactFlowInstance } =
		useContext(typesContext);
	const reactFlowWrapper = useRef(null);

	const { setExtraComponent, setExtraNavigation } = useContext(locationContext);
	const { setErrorData } = useContext(alertContext);
	const [nodes, setNodes, onNodesChange] = useNodesState(
		flow.data?.nodes ?? []
	);
	const [edges, setEdges, onEdgesChange] = useEdgesState(
		flow.data?.edges ?? []
	);
	const { setViewport } = useReactFlow();

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
		(s:EdgeChange[]) => {
			onEdgesChange(s);
			setNodes((x) => {
				let newX = _.cloneDeep(x);
				return newX;
			});
		},
		[onEdgesChange, setNodes]
	);

	const onConnect = useCallback(
		(params:Connection) => {
			setEdges((eds) =>
				addEdge({ ...params, className: "animate-pulse" }, eds)
			);
			setNodes((x) => {
				let newX = _.cloneDeep(x);
				return newX;
			});
		},
		[setEdges, setNodes]
	);

	const onDragOver = useCallback((event:React.DragEvent) => {
		event.preventDefault();
		event.dataTransfer.dropEffect = "move";
	}, []);

	const onDrop = useCallback(
		(event:React.DragEvent) => {
			event.preventDefault();
	
			// Helper function to generate a unique node ID
			function getId() {
				return `dndnode_` + incrementNodeId();
			}
	
			// Get the current bounds of the ReactFlow wrapper element
			const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();
	
			// Extract the data from the drag event and parse it as a JSON object
			let data:{type:string,node?:APIClassType} = JSON.parse(event.dataTransfer.getData("json"));
	
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
				const newNode:NodeType = {
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
		[incrementNodeId, reactFlowInstance, setErrorData, setNodes]
	);

	
	const onDelete = (mynodes) => {
		setEdges(edges.filter((ns) => !nodes.some((n) => ns.source === n.id || ns.target === n.id)));
	}

	return (
		<div className="w-full h-full" ref={reactFlowWrapper}>
			{Object.keys(types).length > 0 ? (
				<>
					<ReactFlow
						nodes={nodes}
						onMove={() =>
							updateFlow({ ...flow, data: reactFlowInstance.toObject() })
						}
						edges={edges}
						onNodesChange={onNodesChange}
						onEdgesChange={onEdgesChangeMod}
						onConnect={onConnect}
						onLoad={setReactFlowInstance}
						onInit={setReactFlowInstance}
						nodeTypes={nodeTypes}
						connectionLineComponent={ConnectionLineComponent}
						onDragOver={onDragOver}
						onDrop={onDrop}
						onNodesDelete={onDelete}
					>
						<Background className="dark:bg-gray-900"/>
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
