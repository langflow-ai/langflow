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
    <div className="flex h-full w-full flex-col">
      <div className="flex w-full flex-row items-center bg-gray-100 px-2 pr-2 text-center dark:bg-gray-800">
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
            className="flex items-center gap-1 border-r border-gray-400 pr-2 text-sm text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
          >
            Code <CodeBracketSquareIcon className="h-5 w-5" />
          </button>
          <button
            onClick={() => openPopUp(<ImportModal />)}
            className="flex items-center gap-1 border-r border-gray-400 pr-2 text-sm text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
          >
            Import <ArrowUpTrayIcon className="h-5 w-5" />
          </button>
          <button
            onClick={() => openPopUp(<ExportModal />)}
            className="flex items-center gap-1 border-r border-gray-400 pr-2  text-sm text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
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
            className="relative text-gray-600 hover:text-gray-500 dark:text-gray-300 dark:hover:text-gray-200"
            onClick={(event: React.MouseEvent<HTMLElement>) => {
              setNotificationCenter(false);
              const top = (event.target as Element).getBoundingClientRect().top;
              const left = (event.target as Element).getBoundingClientRect()
                .left;
              openPopUp(
                <>
                  <div
                    className="absolute z-10"
                    style={{ top: top + 34, left: left - AlertWidth }}
                  >
                    <AlertDropdown />
                  </div>
                  <div className="fixed left-0 top-0 h-screen w-screen"></div>
                </>
              );
            }}
          >
            {notificationCenter && (
              <div className="absolute right-[3px] h-1.5 w-1.5 rounded-full bg-red-600"></div>
            )}
            <BellIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="h-full w-full">
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
