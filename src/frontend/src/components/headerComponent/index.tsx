import { SunIcon, MoonIcon, BellIcon, Home, Users2 } from "lucide-react";
import { useContext, useState, useEffect } from "react";
import { FaGithub } from "react-icons/fa";
import { Button } from "../ui/button";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import MenuBar from "./components/menuBar";
import { Link, useLocation, useParams } from "react-router-dom";

export default function Header() {
  const { flows, addFlow, tabId } = useContext(TabsContext);
  const { openPopUp } = useContext(PopUpContext);
  const { templates } = useContext(typesContext);
  const { id } = useParams();
  const AlertWidth = 384;
  const { dark, setDark } = useContext(darkContext);
  const { notificationCenter, setNotificationCenter, setErrorData } =
    useContext(alertContext);
  const location = useLocation();
  return (
    <div className="w-full h-12 flex justify-between items-center border-b bg-muted">
      <div className="flex gap-2 justify-start items-center w-96">
        <Link to="/">
          <span className="text-2xl ml-4">⛓️</span>
        </Link>
        {flows.findIndex((f) => tabId === f.id) !== -1 && tabId !== "" && (
          <MenuBar flows={flows} tabId={tabId} />
        )}
      </div>
      <div className="flex gap-2 items-center">
        <Link to="/">
          <Button
            className="gap-2"
            variant={location.pathname === "/" ? "primary" : "secondary"}
            size="sm"
          >
            <Home className="w-4 h-4" />
            <div className="flex-1">My Projects</div>
          </Button>
        </Link>
        <Link to="/community">
          <Button
            className="gap-2"
            variant={
              location.pathname === "/community" ? "primary" : "secondary"
            }
            size="sm"
          >
            <Users2 className="w-4 h-4" />
            <div className="flex-1">Community Examples</div>
          </Button>
        </Link>
      </div>
      <div className="flex justify-end px-2 w-96">
        <div className="ml-auto mr-2 flex gap-5">
          <Button
            asChild
            variant="outline"
            className="text-medium-dark-gray dark:text-medium-low-gray "
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
          {/* <button
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
          </button> */}
          <button
            className="text-medium-dark-gray hover:text-medium-gray dark:text-medium-low-gray dark:hover:text-light-gray relative"
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
          {/* <button>
            <img
              src="https://github.com/shadcn.png"
              className="rounded-full w-8"
            />
          </button> */}
        </div>
      </div>
    </div>
  );
}
