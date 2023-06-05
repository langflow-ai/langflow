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
import {
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  ChevronDownIcon,
  CodeBracketSquareIcon,
  GlobeAltIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import ImportModal from "../../modals/importModal";
import ExportModal from "../../modals/exportModal";
import ApiModal from "../../modals/ApiModal";
import { Separator } from "../../components/ui/separator";
import { Button } from "../../components/ui/button";
import { FaGithub } from "react-icons/fa";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";

export default function HomePage() {
  const {
    flows,
    addFlow,
    removeFlow,
    tabIndex,
    setTabIndex,
    uploadFlow,
    downloadFlow,
  } = useContext(TabsContext);
  const { openPopUp } = useContext(PopUpContext);
  const { templates } = useContext(typesContext);
  const AlertWidth = 384;
  const { dark, setDark } = useContext(darkContext);
  const [activeTab, setActiveTab] = useState("myflow");
  const { notificationCenter, setNotificationCenter } =
    useContext(alertContext);
  useEffect(() => {
    //create the first flow
    if (flows.length === 0 && Object.keys(templates).length > 0) {
      addFlow();
    }
  }, [addFlow, flows.length, templates]);
  return (
    flows.length !== 0 && (
      <Tabs
        defaultValue="myflow"
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full h-full flex flex-col"
      >
        <TabsList className="w-full flex justify-between items-center border-b">
          <div className="flex gap-2 justify-start w-96">
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 text-xl bg-foreground px-2 py-1 font-semibold text-secondary">
                <span className="text-2xl">⛓️</span>{" "}
                <ChevronDownIcon className="w-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-40">
                <DropdownMenuLabel>Flow</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => {
                    openPopUp(<ImportModal />);
                  }}
                >
                  <ArrowUpTrayIcon className="w-4 h-4 mr-2" />
                  Import
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    openPopUp(<ExportModal />);
                  }}
                >
                  <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                  Export
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    openPopUp(<ApiModal flowName={flows[tabIndex].name} />);
                  }}
                >
                  <CodeBracketSquareIcon className="w-4 h-4 mr-2" />
                  Code
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <div className="flex gap-2 p-2">
              <TabsTrigger value="myflow" className="flex items-center gap-2">
                {flows[tabIndex].name}
                <DropdownMenu>
                  <DropdownMenuTrigger>
                    <ChevronDownIcon className="w-3" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-40">
                    <DropdownMenuRadioGroup
                      value={tabIndex.toString()}
                      onValueChange={(value) => {
                        setTabIndex(parseInt(value));
                      }}
                    >
                      {flows.map((flow, idx) => {
                        return (
                          <DropdownMenuRadioItem value={idx.toString()}>
                            {flow.name}
                          </DropdownMenuRadioItem>
                        );
                      })}
                    </DropdownMenuRadioGroup>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => {
                        addFlow();
                      }}
                    >
                      <PlusIcon className="w-4 h-4 mr-2" />
                      Add Flow
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TabsTrigger>
            </div>
          </div>
          <div className="flex">
            <TabsTrigger value="community">Explore</TabsTrigger>
            <TabsTrigger value="myflows">My Flows</TabsTrigger>
          </div>
          <div className="flex justify-end px-2 w-96">
            <div className="ml-auto mr-2 flex gap-5">
              <Button
                asChild
                variant="outline"
                className="text-gray-600 dark:text-gray-300"
              >
                <a
                  href="https://github.com/logspace-ai/langflow"
                  target="_blank"
                  rel="noreferrer"
                  className="flex"
                >
                  <FaGithub className="h-5 w-5 mr-2" />
                  Join The Community
                </a>
              </Button>
              <button
                className="text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
                onClick={() => {
                  setDark(!dark);
                }}
              >
                {dark ? (
                  <SunIcon className="h-5 w-5" />
                ) : (
                  <MoonIcon className="h-5 w-5" />
                )}
              </button>
              <button
                className="text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200 relative"
                onClick={(event: React.MouseEvent<HTMLElement>) => {
                  setNotificationCenter(false);
                  const top = (event.target as Element).getBoundingClientRect()
                    .top;
                  const left = (event.target as Element).getBoundingClientRect()
                    .left;
                  openPopUp(
                    <>
                      <div
                        className="z-10 absolute"
                        style={{ top: top + 34, left: left - AlertWidth }}
                      >
                        <AlertDropdown />
                      </div>
                      <div className="h-screen w-screen fixed top-0 left-0"></div>
                    </>
                  );
                }}
              >
                {notificationCenter && (
                  <div className="absolute w-1.5 h-1.5 rounded-full bg-destructive right-[3px]"></div>
                )}
                <BellIcon className="h-5 w-5" aria-hidden="true" />
              </button>
              <button>
                <img
                  src="https://github.com/shadcn.png"
                  className="rounded-full w-8"
                />
              </button>
            </div>
          </div>
        </TabsList>

        <TabsContent value="myflow" className="w-full h-full">
          <div className="h-full w-full flex basis-auto flex-1 overflow-hidden">
            <ExtraSidebar />
            <main className="h-full w-full flex-1 border-t border-gray-200 dark:border-gray-700 flex">
              {/* Primary column */}
              <div className="w-full h-full">
                <ReactFlowProvider>
                  {flows[tabIndex] ? (
                    <FlowPage flow={flows[tabIndex]}></FlowPage>
                  ) : (
                    <></>
                  )}
                </ReactFlowProvider>
              </div>
            </main>
          </div>
        </TabsContent>
        <TabsContent value="myflows" className="w-full h-full bg-muted">
          <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {flows.map((flow, idx) => (
              <Card className="group">
                <CardHeader>
                  <CardTitle className="flex justify-between items-center h-6">
                    {flow.name}
                    <button
                      onClick={() => {
                        removeFlow(flow.id);
                      }}
                    >
                      <TrashIcon className="w-5 text-primary hidden group-hover:block " />
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardFooter>
                  <Button
                    variant="outline"
                    className=""
                    onClick={() => {
                      setTabIndex(idx);
                      setActiveTab("myflow");
                    }}
                  >
                    Open Flow
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    )
  );
}
