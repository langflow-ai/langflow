import { Home, MoonIcon, SunIcon, Users2 } from "lucide-react";
import { useContext, useEffect, useState } from "react";
import { FaDiscord, FaGithub, FaTwitter } from "react-icons/fa";
import { Button } from "../ui/button";
import { TabsContext } from "../../contexts/tabsContext";
import AlertDropdown from "../../alerts/alertDropDown";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import MenuBar from "./components/menuBar";
import { Link, useLocation, useParams } from "react-router-dom";
import { USER_PROJECTS_HEADER } from "../../constants";
import { getRepoStars } from "../../controllers/API";
import { Separator } from "../ui/separator";
import { Bell } from "lucide-react";

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
    <div className="flex h-12 w-full items-center justify-between border-b bg-muted">
      <div className="flex w-96 items-center justify-start gap-2">
        <Link to="/">
          <span className="ml-4 text-2xl">⛓️</span>
        </Link>
        {flows.findIndex((f) => tabId === f.id) !== -1 && tabId !== "" && (
          <MenuBar flows={flows} tabId={tabId} />
        )}
      </div>
      <div className="flex items-center gap-2">
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
      <div className="flex w-96 justify-end px-2">
        <div className="ml-auto mr-2 flex items-center gap-5">
          <a
            href="https://github.com/logspace-ai/langflow"
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center justify-center rounded-md border border-input px-3 pr-0 text-sm font-medium text-muted-foreground shadow-sm ring-offset-background  hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          >
            <FaGithub className="mr-2 h-5 w-5" />
            Star
            <div className="-mr-px ml-2 flex h-9 items-center justify-center rounded-md rounded-l-none border bg-background px-2 text-sm">
              {stars}
            </div>
          </a>
          <a
            href="https://twitter.com/logspace_ai"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground"
          >
            <FaTwitter className="h-5 w-5 hover:text-accent-foreground" />
          </a>
          <a
            href="https://discord.gg/EqksyE2EX9"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground"
          >
            <FaDiscord className="h-5 w-5 hover:text-accent-foreground" />
          </a>

          <Separator orientation="vertical" />
          <button
            className="text-muted-foreground hover:text-accent-foreground "
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
            className="relative text-muted-foreground hover:text-accent-foreground"
            onClick={(event: React.MouseEvent<HTMLElement>) => {
              setNotificationCenter(false);
              const { top, left } = (
                event.target as Element
              ).getBoundingClientRect();
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
              <div className="absolute right-[3px] h-1.5 w-1.5 rounded-full bg-destructive"></div>
            )}
            <Bell className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
