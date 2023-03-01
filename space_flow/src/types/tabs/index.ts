import { flow } from "../flow";

export type TabsContextType = {
	tabIndex: number;
	setTabIndex: (index: number) => void;
	flows: Array<flow>;
	removeFlow: (id: string) => void;
	addFlow: (flowData?: any) => void;
	updateFlow: (newFlow: flow) => void;
	incrementNodeId: () => number;
	downloadFlow: () => void;
	uploadFlow: () => void;
};