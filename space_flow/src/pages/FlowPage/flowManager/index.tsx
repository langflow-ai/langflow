import { useContext, useEffect, useState } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import FlowPage from '..';
import { TabsContext } from '../../../contexts/tabsContext';
import TabComponent from './tabComponent';
var _ = require("lodash");

export function TabsManager(){
  const {flows,addFlow,tabIndex,setTabIndex} = useContext(TabsContext);
  useEffect(()=>{
    if(flows.length===0){
      addFlow({name:"untitled",flow:null,id:_.uniqueId()})
      addFlow({name:"untitle",flow:null,id:_.uniqueId()})
    }
  },[])
  
  return(
    <div className="h-full w-full flex flex-col">
      <div className="w-full flex pr-2 flex-row text-center items-center">
        {flows.map((flow,index)=>{
          return(<TabComponent selected={index===tabIndex} key={index}><div onClick={()=>setTabIndex(index)}>{flow.name}</div></TabComponent>)
        })}
      </div>
      <div className='w-full h-full'>
        {flows.map((flow,index)=>{
          return(
            <div key={index} className={'w-full h-full'} style={{display:index!==tabIndex?"none":""}}>
              
                <FlowPage></FlowPage>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/*
tabs initial logic
TO DO
- create a context with the tabs control so tabs can be changed inside the flow
- create a logic to save tabs and flow state for multitabs and each flow inside each tab
- think about the save logic and how to implement it the best way
- define what each tab will need to show and how it will be displayed

*/
