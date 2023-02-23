import { ReactEventHandler, createContext, useState } from "react";
import { ReactFlowInstance } from "reactflow";

type typesContextType=
{
    reactFlowInstance: ReactFlowInstance;
    setReactFlowInstance: any;
    types: {};
    setTypes:(newState:{})=>void;
}

const initialValue= {
    reactFlowInstance: null,
    setReactFlowInstance: ()=>{},
    types: {},
    setTypes:()=>{},
}

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({children}){
    const [types, setTypes] = useState({});
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    return (
        <typesContext.Provider value={{ types, setTypes, reactFlowInstance, setReactFlowInstance}}>
            {children}
        </typesContext.Provider>
    )
}
