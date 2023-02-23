import { useContext, useEffect, useState } from "react";
import { Tab, Tabs, TabList, TabPanel } from "react-tabs";
import { ReactFlowProvider } from "reactflow";
import FlowPage from "..";
import { TabsContext } from "../../../contexts/tabsContext";
import TabComponent from "./tabComponent";
import { PlusIcon } from '@heroicons/react/24/outline';
var _ = require("lodash");

export function TabsManager() {
	const { flows, addFlow, tabIndex, setTabIndex } = useContext(TabsContext);
  const [inputMode,setInputMode] = useState(false)
	useEffect(() => {
		if (flows.length === 0) {
      const id = _.uniqueId()
			addFlow({ name: "flow "+id, data: null, id });
		}
	}, []);

	return (
		<div className="h-full w-full flex flex-col">
			<div className="w-full flex pr-2 flex-row text-center items-center">
				{flows.map((flow, index) => {
          console.log(tabIndex)
					return (
						<TabComponent onClick={() => setTabIndex(index)} selected={index === tabIndex} key={index} id={flow.id}>
							<div onClick={()=>setInputMode(true)}>{flow.name}</div>
						</TabComponent>
					);
				})}
        <div onClick={()=>{
          const id = _.uniqueId()
          addFlow({ name: "flow"+id, data: null, id})}} className="cursor-pointer"><PlusIcon color="black" width={24}></PlusIcon></div>
			</div>
			<div className="w-full h-full">
				<ReactFlowProvider>
					<FlowPage flow={flows[tabIndex]}></FlowPage>
				</ReactFlowProvider>
			</div>
		</div>
	);
}
