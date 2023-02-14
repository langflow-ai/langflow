import { createContext, useState } from "react";

type locationContextType=
{
    atual:Array<string>;
    setAtual:(newState:Array<string>)=>void;
    isStackedOpen: boolean;
    setIsStackedOpen:(newState:boolean)=>void;
    showSideBar:boolean;
    setShowSideBar:(newState:boolean)=>void;
    extraNavigation:{title:string, options?:Array<{name:string, href:string, icon: any, children?:Array<any>}>};
    setExtraNavigation:(newState:{title:string, options?:Array<{name:string, href:string, icon: any, children?:Array<any>}>}) => void;
    extraComponent:any;
    setExtraComponent:(newState:any) => void;
}

const initialValue= {
    atual : window.location.pathname.replace(/\/$/g, '').split("/"),
    isStackedOpen:((window.innerWidth > 1024 && window.location.pathname.split("/")[1]) ? true : false),
    setAtual: ()=>{},
    setIsStackedOpen:()=>{},
    showSideBar: window.location.pathname.split("/")[1]?true:false,
    setShowSideBar:()=>{},
    extraNavigation: {title:""},
    setExtraNavigation:()=>{},
    extraComponent: <></>,
    setExtraComponent:()=>{},
}



export const locationContext = createContext<locationContextType>(initialValue);

export function LocationProvider({children}){
    const [atual,setAtual] = useState(initialValue.atual)
    const [isStackedOpen,setIsStackedOpen] = useState(initialValue.isStackedOpen)
    const [showSideBar,setShowSideBar] = useState(initialValue.showSideBar)
    const [extraNavigation, setExtraNavigation] = useState({title:""})
    const [extraComponent, setExtraComponent] = useState(<></>)
    return (
        <locationContext.Provider value={{isStackedOpen,setIsStackedOpen,atual,setAtual, showSideBar, setShowSideBar,extraNavigation, setExtraNavigation, extraComponent, setExtraComponent}}>
            {children}
        </locationContext.Provider>
    )
}
