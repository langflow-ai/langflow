import { createContext, useState } from "react";

type flow={name:string,id:string,data:any}

type TabsContextType={
    tabIndex:number;
    setTabIndex:(index:number)=>void;
    flows:Array<flow>
    removeFlow:(id:string)=>void;
    addFlow:(newFlow:flow)=>void;
    updateFlow:(newFLow:flow)=>void;
}

const TabsContextInitialValue = {
    tabIndex : 0,
    setTabIndex:(index:number)=>{},
    flows:[],
    removeFlow:(id:string)=>{},
    addFlow:(newFlow:flow)=>{},
    updateFlow:(newFLow:flow)=>{}
    

}

export const TabsContext = createContext<TabsContextType>(TabsContextInitialValue)

export function TabsProvider({children}){
    const [tabIndex,setTabIndex] = useState(0)
    const [flows,setFlows] = useState<Array<flow>>([])
    function removeFlow(id:string){
        setFlows(prevState=>{
            const newFlows = [...prevState];
            const index = newFlows.findIndex(flow=>flow.id===id)
            if(index!==-1){
                newFlows.splice(index,1)
            }
            if(index===tabIndex){
                if(tabIndex===0){
                    //
                }
                else{
                    setTabIndex(tabIndex-1)
                }
            }
            window.sessionStorage.setItem('tabs', JSON.stringify(newFlows));
            return newFlows;
        })
    }
    function addFlow(newFlow: flow) {
        setFlows(prevState => {
          const newFlows = [...prevState, newFlow];
          window.sessionStorage.setItem('tabs', JSON.stringify(newFlows));
          return newFlows;
        });
      }
    function updateFlow(newFlow:flow){
        setFlows(prevState=>{
            const newFlows = [...prevState];
            const index = newFlows.findIndex(flow=>flow.id===newFlow.id)
            if(index!==-1){
                newFlows[index].data = newFlow.data
                newFlows[index].name = newFlow.name
            }
            window.sessionStorage.setItem('tabs', JSON.stringify(newFlows));
            return newFlows;
        });
    }

    return(
        <TabsContext.Provider value={{tabIndex,setTabIndex,flows,removeFlow,addFlow,updateFlow}}>
            {children}
        </TabsContext.Provider>
    )
}