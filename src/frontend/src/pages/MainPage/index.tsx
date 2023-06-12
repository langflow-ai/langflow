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
    removeFlow,
    setTabId,
  } = useContext(TabsContext);
  return (
      <div
        className="w-full h-full flex flex-col bg-muted"
      >
          <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {Object.keys(flows).map((flow, idx) => (
              <CardComponent
                flow={flows[flow]}
                id={flow}
                removeFlow={removeFlow}
                setTabId={setTabId}
              />
            ))}
          </div>
      </div>
  );
}
