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
import { SunIcon, MoonIcon, BellIcon, GithubIcon, Download, Upload, Plus } from "lucide-react";
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
import { CardComponent } from "./components/cardComponent";
import { MenuBar } from "../../components/headerComponent/components/menuBar";
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
        className="w-full h-full flex overflow-auto flex-col bg-muted"
      >
          <div className="w-full flex justify-between py-12 px-8">
            <span className="text-xl font-semibold">
              Flows
            </span>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => {
                downloadFlows();
              }}>
              <Download className="w-4 mr-2" />
              Download Database
              </Button>
              <Button variant="outline" onClick={() => {uploadFlows();}}>
              <Upload className="w-4 mr-2" />
              Upload Database
              </Button>
              <Button variant="outline" onClick={() => {addFlow();}}>
              <Plus className="w-4 mr-2" />
              Add Flow
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
