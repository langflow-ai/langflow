import { ReactEventHandler, createContext, useState } from "react";
import { ReactFlowInstance } from "reactflow";

type typesContextType=
{
    reactFlowInstance: ReactFlowInstance;
    setReactFlowInstance: any;
    deleteNode:(idx:number)=>void;
    types: {};
    setTypes:(newState:{})=>void;

}

const initialValue= {
    reactFlowInstance: null,
    setReactFlowInstance: ()=>{},
    deleteNode: ()=>{},
    types: {},
    setTypes:()=>{},
}

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({children}){
    const [types, setTypes] = useState({});
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    function deleteNode(idx){
        reactFlowInstance.setNodes(
            reactFlowInstance.getNodes().filter((n) => n.id !== idx)
          );
    }
    return (
        <typesContext.Provider value={{ types, setTypes, reactFlowInstance, setReactFlowInstance, deleteNode}}>
            {children}
        </typesContext.Provider>
    )
}
