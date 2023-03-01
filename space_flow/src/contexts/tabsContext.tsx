import { createContext, useEffect, useState, useRef, ReactNode } from "react";
import {FlowType} from "../types/flow"
import { TabsContextType } from "../types/tabs";



const TabsContextInitialValue:TabsContextType = {
	tabIndex: 0,
	setTabIndex: (index: number) => {},
	flows: [],
	removeFlow: (id: string) => {},
	addFlow: (flowData?: any) => {},
	updateFlow: (newFlow: FlowType) => {},
	incrementNodeId: () => 0,
	downloadFlow: () => {},
	uploadFlow: () => {},
};

export const TabsContext = createContext<TabsContextType>(
	TabsContextInitialValue
);

let _ = require("lodash");

export function TabsProvider({ children }:{children:ReactNode}) {
	const [tabIndex, setTabIndex] = useState(0);
	const [flows, setFlows] = useState<Array<FlowType>>([]);
	const [id, setId] = useState(0);

	const newNodeId = useRef(0);
	function incrementNodeId() {
		newNodeId.current = newNodeId.current + 1;
		return newNodeId.current;
	}
	useEffect(() => {
		if (flows.length !== 0)
			window.localStorage.setItem(
				"tabsData",
				JSON.stringify({ tabIndex, flows, id, nodeId: newNodeId.current })
			);
	}, [flows, id, tabIndex, newNodeId]);

	useEffect(() => {
		let cookie = window.localStorage.getItem("tabsData");
		if (cookie) {
			let cookieObject = JSON.parse(cookie);
			setTabIndex(cookieObject.tabIndex);
			setFlows(cookieObject.flows);
			setId(cookieObject.id);
			newNodeId.current = cookieObject.nodeId;
		}
	}, []);

	function downloadFlow() {
		const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
			JSON.stringify(flows[tabIndex])
		)}`;
		const link = document.createElement("a");
		link.href = jsonString;
		link.download = `${flows[tabIndex].name}.json`;
		link.click();
	}

	function uploadFlow() {
		const input = document.createElement("input");
		input.type = "file";
		input.onchange = (e: Event) => {
			if ((e.target as HTMLInputElement).files[0].type === "application/json") {
				const file = (e.target as HTMLInputElement).files[0];
				file.text().then((text) => {
					addFlow(JSON.parse(text));
				});
			}
		};
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
	function addFlow(flow?: FlowType) {
		const data = flow?.data ? flow.data : null;
		let newFlow: FlowType = {
			name: flow ? flow.name : "flow" + id,
			id: id.toString(),
			data,
			chat: flow ? flow.chat : [],
		};
		setId((old) => old + 1);
		setFlows((prevState) => {
			const newFlows = [...prevState, newFlow];
			return newFlows;
		});
		setTabIndex(flows.length);
	}
	function updateFlow(newFlow: FlowType) {
		setFlows((prevState) => {
			const newFlows = [...prevState];
			const index = newFlows.findIndex((flow) => flow.id === newFlow.id);
			if (index !== -1) {
				newFlows[index].data = newFlow.data;
				newFlows[index].name = newFlow.name;
				newFlows[index].chat = newFlow.chat;
			}
			return newFlows;
		});
	}

	return (
		<TabsContext.Provider
			value={{
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
