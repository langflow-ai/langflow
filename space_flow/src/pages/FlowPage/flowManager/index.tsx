import { useContext, useEffect } from "react";
import { ReactFlowProvider } from "reactflow";
import FlowPage from "..";
import { TabsContext } from "../../../contexts/tabsContext";
import TabComponent from "./tabComponent";
import { example } from "../../../data_assets/example";
var _ = require("lodash");

export function TabsManager() {
  const { flows, addFlow, tabIndex, setTabIndex } = useContext(TabsContext);
  useEffect(() => {
    if (flows.length === 0) {
      addFlow();
    }
  }, [addFlow, flows.length]);

  return (
    <div className="h-full w-full flex flex-col">
      <div className="w-full flex pr-2 flex-row text-center items-center bg-gray-100 px-2">
        {flows.map((flow, index) => {
          return (
            <TabComponent
              onClick={() => setTabIndex(index)}
              selected={index === tabIndex}
              key={index}
              flow={flow}
            />
          );
        })}
        <TabComponent
          onClick={() => {
            addFlow();
          }}
          selected={false}
          flow={null}
        />
      </div>
      <div className="w-full h-full">
        <ReactFlowProvider>
          {flows[tabIndex] ? (
            <FlowPage flow={flows[tabIndex]}></FlowPage>
          ) : (
            <></>
          )}
        </ReactFlowProvider>
      </div>
    </div>
  );
}
