import { createContext, useState } from "react";

type typesContextType=
{
    types: {};
    setTypes:(newState:{})=>void;
}

const initialValue= {
    types: {},
    setTypes:()=>{},
}

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({children}){
    const [types, setTypes] = useState({});
    return (
        <typesContext.Provider value={{ types, setTypes}}>
            {children}
        </typesContext.Provider>
    )
}
