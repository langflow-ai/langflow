import SidebarButton from "./sidebarButton";
import { BsPlusSquare } from "react-icons/bs";
import { classNames } from "../../utils";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useContext, useState } from "react";
import { sidebarNavigation } from "../../entities/sidebarNav";
import { locationContext } from "../../contexts/locationContext";

export default function Sidebar() {
  let { showSideBar, isStackedOpen, setIsStackedOpen } =
    useContext(locationContext);
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  let current = false;
  return (
    <div
      className={
        (showSideBar ? "w-20" : "w-0") +
        " h-full overflow-hidden flex-col transition-all duration-500"
      }
    >
      <div className="w-20 h-full">
        <nav
          aria-label="Sidebar"
          className="h-full overflow-y-auto bg-gray-800"
        >
          <div className="flex flex-col h-full justify-between">
            <div className="relative flex w-20 flex-col space-y-3 p-3">
              {sidebarNavigation.map((item, index) => (
                <SidebarButton item={item} key={index}></SidebarButton>
              ))}
            </div>
            <div className="relative flex w-20 flex-col items-center space-y-3 align-items: center;">
              <button
                key="New Project"
                onClick={() => {
                  setNewProjectOpen(true);
                }}
                className={classNames(
                  current
                    ? "bg-gray-900 text-white"
                    : "text-gray-400 hover:bg-gray-700",
                  "flex-shrink-0 inline-flex items-center justify-center h-14 w-14 rounded-lg"
                )}
              >
                <span className="sr-only">"New Project"</span>
                <BsPlusSquare className="h-8 w-8" aria-hidden="true" />
              </button>
              <div
                className={` ${
                  isStackedOpen ? "h-0" : "h-12"
                } overflow-hidden transition-all duration-500`}
              >
                <div className="h-10">
                  <button
                    className="text-gray-400 flex-shrink-0 inline-flex items-center justify-center rounded-lg"
                    onClick={() => setIsStackedOpen(true)}
                  >
                    <ChevronRightIcon className="h-6 w-6"></ChevronRightIcon>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </nav>
      </div>
    </div>
  );
}
