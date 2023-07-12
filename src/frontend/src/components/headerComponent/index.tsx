import { Bell, Home, MoonIcon, SunIcon, Users2 } from "lucide-react";
import { useContext, useEffect, useState } from "react";
import { FaDiscord, FaGithub, FaTwitter } from "react-icons/fa";
import { Link, useLocation, useParams } from "react-router-dom";
import AlertDropdown from "../../alerts/alertDropDown";
import { USER_PROJECTS_HEADER } from "../../constants";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import { getRepoStars } from "../../controllers/API";
import { Button } from "../ui/button";
import { Separator } from "../ui/separator";
import MenuBar from "./components/menuBar";

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

  const [stars, setStars] = useState(null);

  useEffect(() => {
    async function fetchStars() {
      const starsCount = await getRepoStars("logspace-ai", "langflow");
      setStars(starsCount);
    }
    fetchStars();
  }, []);
  return (
    <div className="header-arrangement">
      <div className="header-start-display">
        <Link to="/">
          <span className="ml-4 text-2xl">⛓️</span>
        </Link>
        {flows.findIndex((f) => tabId === f.id) !== -1 && tabId !== "" && (
          <MenuBar flows={flows} tabId={tabId} />
        )}
      </div>
      <div className="round-button-div">
        <Link to="/">
          <Button
            className="gap-2"
            variant={location.pathname === "/" ? "primary" : "secondary"}
            size="sm"
          >
            <Home className="h-4 w-4" />
            <div className="flex-1">{USER_PROJECTS_HEADER}</div>
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
            <Users2 className="h-4 w-4" />
            <div className="flex-1">Community Examples</div>
          </Button>
        </Link>
      </div>
      <div className="header-end-division">
        <div className="header-end-display">
          <a
            href="https://github.com/logspace-ai/langflow"
            target="_blank"
            rel="noreferrer"
            className="header-github-link"
          >
            <FaGithub className="mr-2 h-5 w-5" />
            Star
            <div className="header-github-display">{stars}</div>
          </a>
          <a
            href="https://twitter.com/logspace_ai"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground"
          >
            <FaTwitter className="side-bar-button-size" />
          </a>
          <a
            href="https://discord.gg/EqksyE2EX9"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground"
          >
            <FaDiscord className="side-bar-button-size" />
          </a>

          <Separator orientation="vertical" />
          <button
            className="extra-side-bar-save-disable"
            onClick={() => {
              setDark(!dark);
            }}
          >
            {dark ? (
              <SunIcon className="side-bar-button-size" />
            ) : (
              <MoonIcon className="side-bar-button-size" />
            )}
          </button>
          <button
            className="extra-side-bar-save-disable relative"
            onClick={(event: React.MouseEvent<HTMLElement>) => {
              setNotificationCenter(false);
              const { top, left } = (
                event.target as Element
              ).getBoundingClientRect();
              openPopUp(
                <>
                  <div
                    className="absolute z-10"
                    style={{ top: top + 40, left: left - AlertWidth }}
                  >
                    <AlertDropdown />
                  </div>
                  <div className="header-notifications-box"></div>
                </>
              );
            }}
          >
            {notificationCenter && <div className="header-notifications"></div>}
            <Bell className="side-bar-button-size" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
