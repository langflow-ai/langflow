import { useContext, useEffect, useState } from "react";
import { FaDiscord, FaGithub, FaTwitter } from "react-icons/fa";
import { Link, useLocation } from "react-router-dom";
import AlertDropdown from "../../alerts/alertDropDown";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { TabsContext } from "../../contexts/tabsContext";
import { getRepoStars } from "../../controllers/API";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Separator } from "../ui/separator";
import MenuBar from "./components/menuBar";

export default function Header() {
  const { flows, tabId } = useContext(TabsContext);
  const { dark, setDark } = useContext(darkContext);
  const { notificationCenter } = useContext(alertContext);
  const location = useLocation();

  const [stars, setStars] = useState(null);

  // Get and set numbers of stars on header
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
        {tabId === "" || !tabId ? (
          <div className="ml-2">
            <a
              href="https://www.langflow.org/"
              target="_blank"
              rel="noreferrer"
              className="header-waitlist-link-box"
            >
              <span className="pr-1 text-2xl">⛓️</span>
              <span>Join The Waitlist</span>
            </a>
          </div>
        ) : (
          <Link to="/">
            <span className="ml-4 text-2xl">⛓️</span>
          </Link>
        )}

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
            <IconComponent name="Home" className="h-4 w-4" />
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
            <IconComponent name="Users2" className="h-4 w-4" />
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
              <IconComponent name="SunIcon" className="side-bar-button-size" />
            ) : (
              <IconComponent name="MoonIcon" className="side-bar-button-size" />
            )}
          </button>
          <AlertDropdown>
            <div className="extra-side-bar-save-disable relative">
              {notificationCenter && (
                <div className="header-notifications"></div>
              )}
              <IconComponent
                name="Bell"
                className="side-bar-button-size"
                aria-hidden="true"
              />
            </div>
          </AlertDropdown>
        </div>
      </div>
    </div>
  );
}
