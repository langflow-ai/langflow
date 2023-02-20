import { useState } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import FlowPage from '..';
import 'react-tabs/style/react-tabs.css';

interface FlowTabProps {
  flow:any;
}

function FlowTab() {
  return (
    <FlowPage></FlowPage>
  );
}

function App() {
  const [flows, setFlows] = useState([]); // Start with one flow
  const [activeIndex, setActiveIndex] = useState(0);

  function onElementsChange(flowIndex: number, elements: any[]) {
    setFlows((prevFlows) => {
      const newFlows = [...prevFlows];
      newFlows[flowIndex] = elements;
      return newFlows;
    });
  }

  function addTab() {
    setFlows([...flows, []]); // Add a new flow to the state
    setActiveIndex(flows.length); // Activate the new tab
  }

  return (
    <Tabs selectedIndex={activeIndex} onSelect={setActiveIndex}>
      <TabList>
        {flows.map((flow, index) => (
          <Tab key={index}>Flow {index + 1}</Tab>
        ))}
        <button onClick={addTab}>+</button> {/* Render the plus button */}
      </TabList>

      {flows.map((flow, index) => (
        <TabPanel key={index}>
          <FlowTab />
        </TabPanel>
      ))}
    </Tabs>
  );
}
/*
tabs initial logic
TO DO
- create a context with the tabs control so tabs can be changed inside the flow
- create a logic to save tabs and flow state for multitabs and each flow inside each tab
- think about the save logic and how to implement it the best way
- define what each tab will need to show and how it will be displayed

*/
