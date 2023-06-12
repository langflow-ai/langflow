import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../../components/ui/tabs";
import ExtraSidebar from "../../components/ExtraSidebarComponent";
import { ReactFlowProvider } from "reactflow";
import FlowPage from "../FlowPage";
import { useContext, useEffect, useState } from "react";
import { SunIcon, MoonIcon, BellIcon, GithubIcon } from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import { Button } from "../../components/ui/button";
import { FaGithub } from "react-icons/fa";

import _ from "lodash";

import { updateFlowInDatabase } from "../../controllers/API";
import { CardComponent } from "./components/cardComponent";
import { MenuBar } from "./components/menuBar";
export default function HomePage() {
  const {
    flows,
    addFlow,
    removeFlow,
    tabIndex,
    setTabIndex,
  } = useContext(TabsContext);
  const { openPopUp } = useContext(PopUpContext);
  const { templates } = useContext(typesContext);
  const AlertWidth = 384;
  const { dark, setDark } = useContext(darkContext);
  const [rename, setRename] = useState(false);
  const { notificationCenter, setNotificationCenter, setErrorData } =
    useContext(alertContext);
  useEffect(() => {
    //create the first flow
    if (flows.length === 0 && Object.keys(templates).length > 0) {
      addFlow();
    }
  }, [addFlow, flows.length, templates]);

  return (
    flows.length !== 0 && (
      <div
        className="w-full h-full flex flex-col bg-muted"
      >
          <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {flows.map((flow, idx) => (
              <CardComponent
                flow={flow}
                idx={idx}
                removeFlow={removeFlow}
                setTabIndex={setTabIndex}
              />
            ))}
          </div>
      </div>
    )
  );
}
