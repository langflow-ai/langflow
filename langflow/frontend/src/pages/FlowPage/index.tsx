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
import ChatInputNode from "../../CustomNodes/ChatInputNode";
import ChatOutputNode from "../../CustomNodes/ChatOutputNode";
import InputNode from "../../CustomNodes/InputNode";
import BooleanNode from "../../CustomNodes/BooleanNode";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import {
	ArrowDownTrayIcon,
	ArrowUpTrayIcon,
} from "@heroicons/react/24/outline";
import ConnectionLineComponent from "./components/ConnectionLineComponent";
import { FlowType, NodeType } from "../../types/flow";
import { APIClassType } from "../../types/api";

const nodeTypes = {
	genericNode: GenericNode,
	inputNode: InputNode,
	chatInputNode: ChatInputNode,
	chatOutputNode: ChatOutputNode,
	booleanNode: BooleanNode,
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
	}, [nodes, edges, reactFlowInstance, flow, updateFlow]);

	useEffect(() => {
		setNodes(flow?.data?.nodes ?? []);
		setEdges(flow?.data?.edges ?? []);
		if (reactFlowInstance) {
			setViewport(flow?.data?.viewport ?? { x: 1, y: 0, zoom: 1 });
		}
	}, [flow, reactFlowInstance, setEdges, setNodes, setViewport]);

	useEffect(() => {
		setExtraComponent(<ExtraSidebar />);
		setExtraNavigation({ title: "Nodes" });
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

			function getId() {
				return `dndnode_` + incrementNodeId();
			}

			const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();
			let data:{type:string,node?:APIClassType} = JSON.parse(event.dataTransfer.getData("json"));
			if (
				data.type !== "chatInput" ||
				(data.type === "chatInput" &&
					!reactFlowInstance.getNodes().some((n) => n.type === "chatInputNode"))
			) {
				const position = reactFlowInstance.project({
					x: event.clientX - reactflowBounds.left,
					y: event.clientY - reactflowBounds.top,
				});
				let newId = getId();

				const newNode:NodeType = {
					id: newId,
					type:
						data.type === "str"
							? "inputNode"
							: data.type === "chatInput"
							? "chatInputNode"
							: data.type === "chatOutput"
							? "chatOutputNode"
							: data.type === "bool"
							? "booleanNode"
							: "genericNode",
					position,
					data: {
						...data,
						id: newId,
						value: null,
					},
				};
				setNodes((nds) => nds.concat(newNode));
			} else {
				setErrorData({
					title: "Error creating node",
					list: ["There can't be more than one chat input."],
				});
			}
		},
		[incrementNodeId, reactFlowInstance, setErrorData, setNodes]
	);

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
					>
						<Background className="dark:bg-gray-900"/>
						<Controls className="[&>button]:text-black  [&>button]:dark:bg-gray-800 hover:[&>button]:dark:bg-gray-700 [&>button]:dark:text-gray-400 [&>button]:dark:fill-gray-400 [&>button]:dark:border-gray-600">
							<ControlButton
								onClick={() => uploadFlow()}
							>
								<ArrowUpTrayIcon />
							</ControlButton>

							<ControlButton
								onClick={() => downloadFlow()}
							>
								<ArrowDownTrayIcon />
							</ControlButton>
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
