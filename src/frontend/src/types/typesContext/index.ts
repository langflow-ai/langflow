import { ReactFlowInstance } from "reactflow";

const types:{[char: string]: string}={}

export type typesContextType = {
	reactFlowInstance: ReactFlowInstance|null;
	setReactFlowInstance: any;
	deleteNode: (idx: string) => void;
	types: typeof types;
	setTypes: (newState: {}) => void;
};