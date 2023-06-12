import { SunIcon, MoonIcon, BellIcon } from "lucide-react";
import { useContext, useState, useEffect } from "react";
import { FaGithub } from "react-icons/fa";
import { Button } from "../ui/button";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import MenuBar from "../../pages/MainPage/components/menuBar";

export default function Header(){
    const {
        flows,
        addFlow,
        removeFlow,
        tabId,
        setTabId,
        uploadFlow,
        downloadFlow,
      } = useContext(TabsContext);
      const { openPopUp } = useContext(PopUpContext);
      const { templates } = useContext(typesContext);
      const AlertWidth = 384;
      const { dark, setDark } = useContext(darkContext);
      const [activeTab, setActiveTab] = useState("myflow");
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
        <div className="w-full h-16 flex justify-between items-center border-b">
          <MenuBar
            activeTab={activeTab}
            setRename={setRename}
            rename={rename}
            flows={flows}
            tabId={tabId}
          />
          <div className="flex">
            <Button>Explore</Button>
            <Button>My Flows</Button>
          </div>
          <div className="flex justify-end px-2 w-96">
            <div className="ml-auto mr-2 flex gap-5">
              <Button
                asChild
                variant="outline"
                className="text-gray-600 dark:text-gray-300 "
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
                  const { top, left } = (
                    event.target as Element
                  ).getBoundingClientRect();
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
        </div>
    )
}