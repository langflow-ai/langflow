import {
	createContext,
	useEffect,
	useState,
	useRef,
	ReactNode,
	useContext,
} from "react";
import { FlowType } from "../types/flow";
import { LangFlowState, TabsContextType } from "../types/tabs";
import { normalCaseToSnakeCase, updateObject, updateTemplate } from "../utils";
import { alertContext } from "./alertContext";
import { typesContext } from "./typesContext";
import { APITemplateType, TemplateVariableType } from "../types/api";
const { v4: uuidv4 } = require("uuid");

const TabsContextInitialValue: TabsContextType = {
	save: () => {},
	tabIndex: 0,
	setTabIndex: (index: number) => {},
	flows: [],
	removeFlow: (id: string) => {},
	addFlow: (flowData?: any) => {},
	updateFlow: (newFlow: FlowType) => {},
	incrementNodeId: () => 0,
	downloadFlow: (flow: FlowType) => {},
	uploadFlow: () => {},
	hardReset: () => {},
	disableCP:false,
	setDisableCP:(state:boolean)=>{},
};

export const TabsContext = createContext<TabsContextType>(
	TabsContextInitialValue
);

export function TabsProvider({ children }: { children: ReactNode }) {
	const { setNoticeData } = useContext(alertContext);
	const [tabIndex, setTabIndex] = useState(0);
	const [flows, setFlows] = useState<Array<FlowType>>([]);
	const [id, setId] = useState("");
	const { templates } = useContext(typesContext);

	const newNodeId = useRef(0);
	function incrementNodeId() {
		newNodeId.current = newNodeId.current + 1;
		return newNodeId.current;
	}
	function save() {
		if (flows.length !== 0)
			window.localStorage.setItem(
				"tabsData",
				JSON.stringify({ tabIndex, flows, id, nodeId: newNodeId.current })
			);
	}
	useEffect(() => {
		//save tabs locally
		save();
	}, [flows, id, tabIndex, newNodeId]);

	useEffect(() => {
		//get tabs locally saved
		let cookie = window.localStorage.getItem("tabsData");
		if (cookie && Object.keys(templates).length > 0) {
			let cookieObject: LangFlowState = JSON.parse(cookie);
			cookieObject.flows.forEach((flow) => {
				flow.data.nodes.forEach((node) => {
					if (Object.keys(templates[node.data.type]["template"]).length > 0) {
						node.data.node.template = updateTemplate(
							templates[node.data.type][
								"template"
							] as unknown as APITemplateType,

							node.data.node.template as APITemplateType
						);
					}
				});
			});
			setTabIndex(cookieObject.tabIndex);
			setFlows(cookieObject.flows);
			setId(cookieObject.id);
			newNodeId.current = cookieObject.nodeId;
		}
	}, [templates]);
	function hardReset() {
		newNodeId.current = 0;
		setTabIndex(0);
		setFlows([]);
		setId("");
	}

	/**
	 * Downloads the current flow as a JSON file
	 */
	function downloadFlow(flow: FlowType) {
		// create a data URI with the current flow data
		const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
			JSON.stringify(flow)
		)}`;

		// create a link element and set its properties
		const link = document.createElement("a");
		link.href = jsonString;
		link.download = `${flows[tabIndex].name}.json`;

		// simulate a click on the link element to trigger the download
		link.click();
		setNoticeData({
			title: "Warning: Critical data,JSON file may including API keys.",
		});
	}

	/**
	 * Creates a file input and listens to a change event to upload a JSON flow file.
	 * If the file type is application/json, the file is read and parsed into a JSON object.
	 * The resulting JSON object is passed to the addFlow function.
	 */
	function uploadFlow() {
		// create a file input
		const input = document.createElement("input");
		input.type = "file";
		// add a change event listener to the file input
		input.onchange = (e: Event) => {
			// check if the file type is application/json
			if ((e.target as HTMLInputElement).files[0].type === "application/json") {
				// get the file from the file input
				const file = (e.target as HTMLInputElement).files[0];
				// read the file as text
				file.text().then((text) => {
					// parse the text into a JSON object
					let flow: FlowType = JSON.parse(text);

					addFlow(flow);
				});
			}
		};
		// trigger the file input click event to open the file dialog
		input.click();
	}
	/**
	 * Removes a flow from an array of flows based on its id.
	 * Updates the state of flows and tabIndex using setFlows and setTabIndex hooks.
	 * @param {string} id - The id of the flow to remove.
	 */
	function removeFlow(id: string) {
		setFlows((prevState) => {
			const newFlows = [...prevState];
			const index = newFlows.findIndex((flow) => flow.id === id);
			if (index >= 0) {
				if (index === tabIndex) {
					setTabIndex(flows.length - 2);
					newFlows.splice(index, 1);
				} else {
					let flowId = flows[tabIndex].id;
					newFlows.splice(index, 1);
					setTabIndex(newFlows.findIndex((flow) => flow.id === flowId));
				}
			}
			return newFlows;
		});
	}
	/**
	 * Add a new flow to the list of flows.
	 * @param flow Optional flow to add.
	 */
	function addFlow(flow?: FlowType) {
		// Get data from the flow or set it to null if there's no flow provided.
		const data = flow?.data ? flow.data : null;
		const description = flow?.description ? flow.description : "";

		if (data) {
			data.nodes.forEach((node) => {
				if (Object.keys(templates[node.data.type]["template"]).length > 0) {
					node.data.node.template = updateTemplate(
						templates[node.data.type]["template"] as unknown as APITemplateType,
						node.data.node.template as APITemplateType
					);
				}
			});
		}
		// Create a new flow with a default name if no flow is provided.
		let newFlow: FlowType = {
			description,
			name: flow?.name ?? "New Flow",
			id: id.toString(),
			data,
		};

		// Increment the ID counter.
		setId(uuidv4());

		// Add the new flow to the list of flows.
		setFlows((prevState) => {
			const newFlows = [...prevState, newFlow];
			return newFlows;
		});

		// Set the tab index to the new flow.
		setTabIndex(flows.length);
	}
	/**
	 * Updates an existing flow with new data
	 * @param newFlow - The new flow object containing the updated data
	 */
	function updateFlow(newFlow: FlowType) {
		setFlows((prevState) => {
			const newFlows = [...prevState];
			const index = newFlows.findIndex((flow) => flow.id === newFlow.id);
			if (index !== -1) {
				newFlows[index].description = newFlow.description ?? "";
				newFlows[index].data = newFlow.data;
				newFlows[index].name = newFlow.name;
			}
			return newFlows;
		});
	}
	const [disableCP, setDisableCP] = useState(false);

	return (
		<TabsContext.Provider
			value={{
				disableCP,
				setDisableCP,
				save,
				hardReset,
				tabIndex,
				setTabIndex,
				flows,
				incrementNodeId,
				removeFlow,
				addFlow,
				updateFlow,
				downloadFlow,
				uploadFlow,
			}}
		>
			{children}
		</TabsContext.Provider>
	);
}
