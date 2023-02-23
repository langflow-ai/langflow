import { createContext, useEffect, useState } from "react";

type flow={name:string,id:string,data:any}

type TabsContextType={
    tabIndex:number;
    setTabIndex:(index:number)=>void;
    flows:Array<flow>
    removeFlow:(id:string)=>void;
    addFlow:()=>void;
    updateFlow:(newFlow:flow)=>void;
    setNodeId:(newState:any)=>void;
    nodeId:number;
}

const TabsContextInitialValue = {
    tabIndex : 0,
    setTabIndex:(index:number)=>{},
    flows:[],
    removeFlow:(id:string)=>{},
    addFlow:()=>{},
    updateFlow:(newFlow:flow)=>{},
    setNodeId:(newState:any)=>{},
    nodeId:0,
    

}

export const TabsContext = createContext<TabsContextType>(TabsContextInitialValue)

export function TabsProvider({children}){
    const [tabIndex,setTabIndex] = useState(0)
    const [flows,setFlows] = useState<Array<flow>>([])
    const [id, setId] = useState(0);
    const [nodeId, setNodeId] = useState(0);
    useEffect(() => {
        if(flows.length !== 0)
            window.localStorage.setItem('tabsData', JSON.stringify({tabIndex, flows, id, nodeId}));
    }, [flows, id, nodeId, tabIndex]);

    useEffect(() => {
        let cookie = window.localStorage.getItem('tabsData');
        if(cookie){
            let cookieObject = JSON.parse(cookie);
            setTabIndex(cookieObject.tabIndex);
            setFlows(cookieObject.flows)
            setId(cookieObject.id)
            setNodeId(cookieObject.nodeId)
        }
    }, [])
    
    function removeFlow(id:string){
        setFlows(prevState=>{
            const newFlows = [...prevState];
            const index = newFlows.findIndex(flow=>flow.id===id);
            if(index >= 0){
                if(index===tabIndex){
                    setTabIndex(flows.length-2);
                    newFlows.splice(index,1);
                } else {
                    let flowId = flows[tabIndex].id;
                    newFlows.splice(index,1);
                    setTabIndex(newFlows.findIndex(flow=>flow.id === flowId));
                }
                
            }
            return newFlows;
        });
    }
    function addFlow() {
        let newFlow: flow = {name: "flow"+id, id: id.toString(), data:null}
        setId((old) => old+1);
        setFlows(prevState => {
            const newFlows = [...prevState, newFlow];
            return newFlows;
        });
        setTabIndex(flows.length);
      }
    function updateFlow(newFlow:flow){
        setFlows(prevState=>{
            const newFlows = [...prevState];
            const index = newFlows.findIndex(flow=>flow.id===newFlow.id)
            if(index!==-1){
                newFlows[index].data = newFlow.data
                newFlows[index].name = newFlow.name
            }
            return newFlows;
        });
    }

    return(
        <TabsContext.Provider value={{tabIndex,setTabIndex,flows,setNodeId, nodeId,removeFlow,addFlow,updateFlow}}>
            {children}
        </TabsContext.Provider>
    )
}