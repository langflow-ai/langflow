import { createContext, ReactNode, useState } from "react";
import { Node} from "reactflow";
import { typesContextType } from "../types/typesContext";

//context to share types adn functions from nodes to flow

const initialValue:typesContextType = {
	reactFlowInstance: null,
	setReactFlowInstance: () => {},
	deleteNode: () => {},
	types: {},
	setTypes: () => {},
};

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({ children }:{children:ReactNode}) {
	const [types, setTypes] = useState({});
	const [reactFlowInstance, setReactFlowInstance] = useState(null);
	function deleteNode(idx:string) {
		reactFlowInstance.setNodes(
			reactFlowInstance.getNodes().filter((n:Node) => n.id !== idx)
		);
		reactFlowInstance.setEdges(reactFlowInstance.getEdges().filter((ns) => ns.source !== idx && ns.target !== idx));
	}
	return (
		<typesContext.Provider
			value={{
				types,
				setTypes,
				reactFlowInstance,
				setReactFlowInstance,
				deleteNode,
			}}
		>
			{children}
		</typesContext.Provider>
	);
}
