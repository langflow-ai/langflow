import { useContext, useEffect } from "react";
import Page from "./components/PageComponent";
import { TabsContext } from "../../contexts/tabsContext";
import { useParams } from "react-router-dom";

export default function FlowPage(){
  const { flows, tabId, setTabId } = useContext(TabsContext);
  const {id} = useParams();
  useEffect(() => {
    setTabId(id);
  }, [id])
  return (
    flows.length > 0 && tabId !== "" && flows.findIndex(flow => flow.id === tabId) !== -1 &&
    <Page flow={flows.find(flow => flow.id === tabId)} />
  )
}