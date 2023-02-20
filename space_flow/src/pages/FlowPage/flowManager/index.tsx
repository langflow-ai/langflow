import { useContext, useState } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import FlowPage from '..';
import { TabsContext } from '../../../contexts/tabsContext';
import TabComponent from './tabComponent';
var _ = require("lodash");

export function TabsManager(){
  const {flows,addFlow} = useContext(TabsContext);
  if(flows.length===0){
    addFlow({name:"untitled",flow:null,id:_.uniqueId()})
  }

  return(
    <Tabs className="h-full w-full flex flex-col">
      <TabList>
        {flows.map(flow=><Tab key={flow.id}><TabComponent>{flow.name}</TabComponent></Tab>)}
        <Tab><button>+</button></Tab>
      </TabList>
      {flows.map(flow=><TabPanel key={flow.id} className="h-full w-full"><FlowPage></FlowPage></TabPanel>)}
    </Tabs>
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
