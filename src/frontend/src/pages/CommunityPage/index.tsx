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
import {
  SunIcon,
  MoonIcon,
  BellIcon,
  GithubIcon,
  Download,
  Upload,
  Plus,
  Home,
  Users2,
} from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import { Button } from "../../components/ui/button";
import { FaGithub } from "react-icons/fa";

import _ from "lodash";

import {
  getExamples,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../../controllers/API";
import { MenuBar } from "../../components/headerComponent/components/menuBar";
import { FlowType } from "../../types/flow";
import { CardComponent } from "./components/cardComponent";
export default function CommunityPage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow } =
    useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);
  function handleExamples() {
    setLoadingExamples(true);
    getExamples()
      .then((result) => {
        setLoadingExamples(false);
        setExamples(result);
      })
      .catch((error) =>
        setErrorData({
          title: "there was an error loading examples, please try again",
          list: [error.message],
        })
      );
  }

  useEffect(() => {
    handleExamples();
  }, []);
  return (
    <div className="w-full h-full flex overflow-auto flex-col bg-muted px-16">
      <div className="w-full flex justify-between py-12 pb-2 px-6">
        <span className="text-2xl flex items-center justify-center gap-2 font-semibold">
          <Users2 className="w-6" />
          Community Examples
        </span>
        <div className="flex gap-2">
          <a href="https://github.com/logspace-ai/langflow_examples">
            <Button variant="primary">
              <GithubIcon className="w-4 mr-2" />
              Add Your Example
            </Button>
          </a>
        </div>
      </div>
      <span className="flex pb-8 px-6 w-[70%] text-muted-foreground">
      Discover and learn from shared examples by the LangFlow community. We welcome new example contributions that can help our community explore new and powerful features.
      </span>
      <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {!loadingExamples &&
          examples.map((flow, idx) => (
            <CardComponent key={idx} flow={flow} id={flow.id} />
          ))}
      </div>
    </div>
  );
}
