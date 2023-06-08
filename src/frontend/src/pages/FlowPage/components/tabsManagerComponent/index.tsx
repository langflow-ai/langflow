import { useContext, useEffect, useState } from "react";
import { ReactFlowProvider } from "reactflow";
import TabComponent from "../tabComponent";
import { TabsContext } from "../../../../contexts/tabsContext";
import FlowPage from "../..";
import { darkContext } from "../../../../contexts/darkContext";
import {
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  BellIcon,
  CodeBracketSquareIcon,
  MoonIcon,
  SunIcon,
} from "@heroicons/react/24/outline";
import { PopUpContext } from "../../../../contexts/popUpContext";
import AlertDropdown from "../../../../alerts/alertDropDown";
import { alertContext } from "../../../../contexts/alertContext";
import ImportModal from "../../../../modals/importModal";
import ExportModal from "../../../../modals/exportModal";
import { typesContext } from "../../../../contexts/typesContext";
import ApiModal from "../../../../modals/ApiModal";

export default function TabsManagerComponent() {
  const { flows, addFlow, tabIndex, setTabIndex, uploadFlow, downloadFlow } =
    useContext(TabsContext);
  const { openPopUp } = useContext(PopUpContext);
  const { templates } = useContext(typesContext);
  const AlertWidth = 384;
  const { dark, setDark } = useContext(darkContext);
  const { notificationCenter, setNotificationCenter } =
    useContext(alertContext);
  useEffect(() => {
    //create the first flow
    if (flows.length === 0 && Object.keys(templates).length > 0) {
      addFlow();
    }
  }, [addFlow, flows.length, templates]);

  return (
    <div className="h-full w-full flex flex-col">
      <div className="w-full flex pr-2 flex-row text-center items-center bg-gray-100 dark:bg-gray-800 px-2">
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
        <div className="ml-auto mr-2 flex gap-3">
          <button
            onClick={() =>
              openPopUp(<ApiModal flowName={flows[tabIndex].name} />)
            }
            className="flex items-center gap-1 pr-2 border-gray-400 border-r text-sm text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
          >
            Code <CodeBracketSquareIcon className="w-5 h-5" />
          </button>
          <button
            onClick={() => openPopUp(<ImportModal />)}
            className="flex items-center gap-1 pr-2 border-gray-400 border-r text-sm text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
          >
            Import <ArrowUpTrayIcon className="w-5 h-5" />
          </button>
          <button
            onClick={() => openPopUp(<ExportModal />)}
            className="flex items-center gap-1 pr-2 text-sm text-gray-600  border-gray-400 border-r hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
          >
            Export <ArrowDownTrayIcon className="h-5 w-5" />
          </button>
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
              const top = (event.target as Element).getBoundingClientRect().top;
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
              <div className="absolute w-1.5 h-1.5 rounded-full bg-red-600 right-[3px]"></div>
            )}
            <BellIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="w-full h-full dark:bg-gray-800">
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
