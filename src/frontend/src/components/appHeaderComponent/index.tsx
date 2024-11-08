import AlertDropdown from "@/alerts/alertDropDown";
import ShadTooltip from "@/components/shadTooltipComponent";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { CustomProductSelector } from "@/customization/components/custom-product-selector";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_NEW_LOGO,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Separator } from "../ui/separator";
import ShortDataStaxLogo from "./assets/ShortDataStaxLogo.svg?react";
import ShortLangFlowIcon from "./assets/ShortLangFlowIcon.svg?react";
import { AccountMenu } from "./components/AccountMenu";
import FlowMenu from "./components/FlowMenu";
import GithubStarComponent from "./components/GithubStarButton";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  const [activeState, setActiveState] = useState<"notifications" | null>(null);
  const lastPath = window.location.pathname.split("/").filter(Boolean).pop();
  const notificationRef = useRef<HTMLButtonElement | null>(null);
  const notificationContentRef = useRef<HTMLDivElement | null>(null);
  useTheme();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      const isNotificationButton = notificationRef.current?.contains(target);
      const isNotificationContent =
        notificationContentRef.current?.contains(target);

      if (!isNotificationButton && !isNotificationContent) {
        setActiveState(null);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className="z-[1] flex h-[62px] w-full items-center justify-between gap-2 border-b px-5 py-2.5 dark:bg-background">
      {/* Left Section */}
      <div className={`flex gap-2`}>
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="flex h-8 w-8 items-center"
          data-testid="icon-ChevronLeft"
        >
          {ENABLE_DATASTAX_LANGFLOW ? (
            <ShortDataStaxLogo className="fill-black dark:fill-[white]" />
          ) : ENABLE_NEW_LOGO ? (
            <ShortLangFlowIcon className="h-5 w-5 fill-black dark:fill-[white]" />
          ) : (
            <span className="fill-black text-2xl dark:fill-white">⛓️</span>
          )}
        </Button>
        {!ENABLE_DATASTAX_LANGFLOW && (
          <>
            <CustomOrgSelector />
            <CustomProductSelector />
          </>
        )}
      </div>

      {/* Middle Section */}
      <div className="w-full flex-1 truncate md:max-w-[57%] lg:absolute lg:left-1/2 lg:max-w-[43%] lg:-translate-x-1/2 xl:max-w-[31%]">
        <FlowMenu />
      </div>

      {/* Right Section */}
      <div className={`flex items-center gap-2`}>
        {!ENABLE_DATASTAX_LANGFLOW && (
          <>
            <Button
              unstyled
              className="hidden items-center whitespace-nowrap 2xl:inline"
              onClick={() =>
                window.open("https://github.com/langflow-ai/langflow", "_blank")
              }
            >
              <GithubStarComponent />
            </Button>
          </>
        )}
        <AlertDropdown
          notificationRef={notificationContentRef}
          onClose={() => setActiveState(null)}
        >
          <ShadTooltip
            content="Notifications and errors"
            side="bottom"
            styleClasses="z-10"
          >
            <Button
              ref={notificationRef}
              variant="ghost"
              className={`relative ${activeState === "notifications" ? "bg-accent text-accent-foreground" : ""}`}
              onClick={() =>
                setActiveState((prev) =>
                  prev === "notifications" ? null : "notifications",
                )
              }
            >
              <span
                className={
                  notificationCenter
                    ? `absolute left-[31px] top-[10px] block h-1 w-1 rounded-full bg-destructive`
                    : "hidden"
                }
              />
              <ForwardedIconComponent
                name="bell"
                className="side-bar-button-size h-[18px] w-[18px]"
                aria-hidden="true"
              />
              <span className="hidden whitespace-nowrap xl:inline">
                Notifications
              </span>
            </Button>
          </ShadTooltip>
        </AlertDropdown>
        {!ENABLE_DATASTAX_LANGFLOW && (
          <>
            <ShadTooltip
              content="Go to LangflowStore"
              side="bottom"
              styleClasses="z-10"
            >
              <Button
                variant="ghost"
                className={` ${lastPath === "store" ? "bg-accent text-accent-foreground" : ""}`}
                onClick={() => {
                  navigate("/store");
                }}
                data-testid="button-store"
              >
                <ForwardedIconComponent
                  name="Store"
                  className="side-bar-button-size h-[18px] w-[18px]"
                />
                <span className="hidden whitespace-nowrap xl:inline">
                  Store
                </span>
              </Button>
            </ShadTooltip>
            <Separator
              orientation="vertical"
              className="my-auto h-7 dark:border-zinc-700"
            />
          </>
        )}
        {ENABLE_DATASTAX_LANGFLOW && (
          <>
            <ShadTooltip content="Docs" side="bottom" styleClasses="z-10">
              <Button
                variant="ghost"
                className="flex text-sm font-medium"
                onClick={() =>
                  window.open(
                    "https://docs.datastax.com/en/langflow/index.html",
                    "_blank",
                  )
                }
              >
                <ForwardedIconComponent
                  name="book-open-text"
                  className="side-bar-button-size h-[18px] w-[18px]"
                  aria-hidden="true"
                />
                Docs
              </Button>
            </ShadTooltip>
            <ShadTooltip content="Settings" side="bottom" styleClasses="z-10">
              <Button
                data-testid="user-profile-settings"
                variant="ghost"
                className="flex text-sm font-medium"
                onClick={() => navigate("/settings")}
              >
                <ForwardedIconComponent
                  name="Settings"
                  className="side-bar-button-size h-[18px] w-[18px]"
                />
                Settings
              </Button>
            </ShadTooltip>
            <Separator
              orientation="vertical"
              className="my-auto h-7 dark:border-zinc-700"
            />
          </>
        )}
        <div className="ml-3 flex">
          <AccountMenu />
        </div>
      </div>
    </div>
  );
}
