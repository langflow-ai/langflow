import { FlowType } from "../flow";

export type TabsContextType = {
	tabIndex: number;
	setTabIndex: (index: number) => void;
	flows: Array<FlowType>;
	removeFlow: (id: string) => void;
	addFlow: (flowData?: any) => void;
	updateFlow: (newFlow: FlowType) => void;
	incrementNodeId: () => number;
	downloadFlow: (flow:FlowType) => void;
	uploadFlow: () => void;
	lockChat:boolean;
	setLockChat:(prevState:boolean)=>void;
	hardReset:()=>void;
};