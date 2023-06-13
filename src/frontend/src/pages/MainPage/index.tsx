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
import { SunIcon, MoonIcon, BellIcon, GithubIcon, Download, Upload, Plus, Home } from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import { Button } from "../../components/ui/button";
import { FaGithub } from "react-icons/fa";

import _ from "lodash";

import { updateFlowInDatabase, uploadFlowsToDatabase } from "../../controllers/API";
import { MenuBar } from "../../components/headerComponent/components/menuBar";
import { CardComponent } from "./components/cardComponent";
export default function HomePage() {
  const {
    flows,
    setTabId,
    downloadFlows,
    uploadFlows,
    addFlow,
  } = useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, [])
  return (
      <div
        className="w-full h-full flex overflow-auto flex-col bg-muted px-16"
      >
          <div className="w-full flex justify-between py-12 pb-8 px-6">
            <span className="text-2xl flex items-center justify-center gap-2 font-semibold">
              <Home className="w-6" />My Projects
            </span>
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => {
                downloadFlows();
              }}>
              <Download className="w-4 mr-2" />
              Download Database
              </Button>
              <Button variant="primary" onClick={() => {uploadFlows();}}>
              <Upload className="w-4 mr-2" />
              Upload Database
              </Button>
              <Button variant="primary" onClick={() => {addFlow();}}>
              <Plus className="w-4 mr-2" />
              New Project
              </Button>
            </div>
          </div>
          <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {flows.map((flow, idx) => (
              <CardComponent
                key={idx}
                flow={flow}
                id={flow.id}
              />
            ))}
          </div>
      </div>
  );
}
