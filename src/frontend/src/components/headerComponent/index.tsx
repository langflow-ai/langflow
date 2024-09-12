import { useContext } from "react";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { RiTwitterXFill } from "react-icons/ri";
import { useLocation } from "react-router-dom";
import AlertDropdown from "../../alerts/alertDropDown";
import {
  BASE_URL_API,
  LOCATIONS_TO_RETURN,
  USER_PROJECTS_HEADER,
} from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";

import { useLogout } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { DOCS_LINK } from "@/customization/config-constants";
import {
  ENABLE_DARK_MODE,
  ENABLE_PROFILE_ICONS,
  ENABLE_SOCIAL_LINKS,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import { useStoreStore } from "../../stores/storeStore";
import IconComponent, { ForwardedIconComponent } from "../genericIconComponent";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Separator } from "../ui/separator";
import MenuBar from "./components/menuBar";

export default function Header(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const location = useLocation();

  const { userData } = useContext(AuthContext);
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const { mutate: mutationLogout } = useLogout();

  const navigate = useCustomNavigate();
  const hasStore = useStoreStore((state) => state.hasStore);

  const dark = useDarkStore((state) => state.dark);
  const setDark = useDarkStore((state) => state.setDark);
  const stars = useDarkStore((state) => state.stars);

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

  const redirectToLastLocation = () => {
    const canGoBack = location.key !== "default";
    if (canGoBack) {
      navigate(-1);
    } else {
      navigate("/", { replace: true });
    }
  };

  const showArrowReturnIcon = LOCATIONS_TO_RETURN.some((path) =>
    location.pathname.includes(path),
  );

  const handleLogout = () => {
    mutationLogout();
  };

  return (
    <div className="header-arrangement relative">
      <div className="header-start-display">
        <CustomLink to="/all" className="cursor-pointer">
          <span className="ml-4 text-2xl">⛓️</span>
        </CustomLink>
        {showArrowReturnIcon && (
          <Button
            unstyled
            onClick={() => {
              redirectToLastLocation();
            }}
          >
            <IconComponent name="ChevronLeft" className="w-4" />
          </Button>
        )}

        <MenuBar />
      </div>

      <div className="flex items-center xl:absolute xl:left-1/2 xl:-translate-x-1/2">
        <CustomLink to="/all">
          <Button
            className="gap-2"
            variant={
              location.pathname.includes("/all") ||
              location.pathname.includes("/components")
                ? "primary"
                : "secondary"
            }
            size="sm"
          >
            <IconComponent name="Home" className="h-4 w-4" />
            <div className="hidden flex-1 lg:block">{USER_PROJECTS_HEADER}</div>
          </Button>
        </CustomLink>

        {hasStore && (
          <CustomLink to="/store">
            <Button
              className="gap-2"
              variant={
                location.pathname.includes("/store") ? "primary" : "secondary"
              }
              size="sm"
              data-testid="button-store"
            >
              <IconComponent name="Store" className="h-4 w-4" />
              <div className="hidden flex-1 lg:block">Store</div>
            </Button>
          </CustomLink>
        )}
      </div>
      <div className="header-end-division">
        <div className="header-end-display">
          {ENABLE_SOCIAL_LINKS && (
            <>
              <a
                href="https://github.com/langflow-ai/langflow"
                target="_blank"
                rel="noreferrer"
                className="header-github-link gap-2"
              >
                <FaGithub className="h-5 w-5" />
                <div className="hidden lg:block">Star</div>
                <div className="header-github-display">{stars ?? 0}</div>
              </a>
              <a
                href="https://twitter.com/langflow_ai"
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground"
              >
                <RiTwitterXFill className="side-bar-button-size" />
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
            </>
          )}
          {ENABLE_DARK_MODE && (
            <button
              className="extra-side-bar-save-disable"
              onClick={() => {
                setDark(!dark);
              }}
            >
              {dark ? (
                <IconComponent
                  name="SunIcon"
                  className="side-bar-button-size"
                />
              ) : (
                <IconComponent
                  name="MoonIcon"
                  className="side-bar-button-size"
                />
              )}
            </button>
          )}
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

          <>
            <Separator orientation="vertical" />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  unstyled
                  data-testid="user-profile-settings"
                  className="shrink-0"
                >
                  {ENABLE_PROFILE_ICONS ? (
                    <img
                      src={profileImageUrl}
                      className="h-7 w-7 shrink-0 focus-visible:outline-0"
                    />
                  ) : (
                    <IconComponent
                      name="Settings"
                      className="side-bar-button-size"
                    />
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="mr-1 mt-1 min-w-40">
                {!autoLogin && (
                  <>
                    <DropdownMenuLabel>
                      <div className="flex items-center gap-3">
                        <img
                          src={profileImageUrl}
                          className="h-5 w-5 focus-visible:outline-0"
                        />

                        {userData?.username ?? "User"}
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuLabel>General</DropdownMenuLabel>
                <DropdownMenuItem
                  className="cursor-pointer gap-2"
                  onClick={() => navigate("/settings")}
                >
                  <ForwardedIconComponent name="Settings" className="w-4" />
                  Settings
                </DropdownMenuItem>
                {!autoLogin && (
                  <>
                    {isAdmin && (
                      <DropdownMenuItem
                        className="cursor-pointer gap-2"
                        onClick={() => navigate("/admin")}
                      >
                        <ForwardedIconComponent name="Shield" className="w-4" />
                        Admin Page
                      </DropdownMenuItem>
                    )}
                  </>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuLabel>Help</DropdownMenuLabel>
                <DropdownMenuItem
                  className="cursor-pointer gap-2"
                  onClick={() =>
                    window.open(
                      DOCS_LINK || "https://docs.langflow.org/",
                      "_blank",
                    )
                  }
                >
                  <ForwardedIconComponent name="FileText" className="w-4" />
                  Docs
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="cursor-pointer gap-2"
                  onClick={() =>
                    window.open(
                      "https://github.com/langflow-ai/langflow/discussions",
                      "_blank",
                    )
                  }
                >
                  <ForwardedIconComponent
                    name="MessagesSquare"
                    className="w-4"
                  />
                  Discussions
                </DropdownMenuItem>
                {!autoLogin && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="cursor-pointer gap-2"
                      onClick={handleLogout}
                    >
                      <ForwardedIconComponent name="LogOut" className="w-4" />
                      Log Out
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        </div>
      </div>
    </div>
  );
}
