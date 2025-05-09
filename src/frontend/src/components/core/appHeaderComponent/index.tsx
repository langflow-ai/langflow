import AlertDropdown from "@/alerts/alertDropDown";
import DataStaxLogo from "@/assets/DataStaxLogo.svg?react";
import LangflowLogo from "@/assets/LangflowLogo.png?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { CustomProductSelector } from "@/customization/components/custom-product-selector";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import { useEffect, useRef, useState } from "react";
import { AccountMenu } from "./components/AccountMenu";
import FlowMenu from "./components/FlowMenu";
import LangflowCounts from "./components/langflow-counts";
import {
  HeaderMenu,
  HeaderMenuItemButton,
  HeaderMenuItemLink,
  HeaderMenuItems,
  HeaderMenuToggle,
} from "./components/HeaderMenu";
import { ThemeButtons } from "./components/ThemeButtons";
import { useLogout } from "@/controllers/API/queries/auth";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  const [activeState, setActiveState] = useState<"notifications" | null>(null);
  const notificationRef = useRef<HTMLButtonElement | null>(null);
  const notificationContentRef = useRef<HTMLDivElement | null>(null);
  const { mutate: mutationLogout } = useLogout();
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

  const handleLogout = () => {
    mutationLogout();
  };

  // useResetDismissUpdateAll();

  const flows = useFlowsManagerStore((state) => state.flows);
  const examples = useFlowsManagerStore((state) => state.examples);
  const folders = useFolderStore((state) => state.folders);

  const isEmpty = flows?.length !== examples?.length || folders?.length > 1;

  const getNotificationBadge = () => {
    const baseClasses = "absolute h-1 w-1 rounded-full bg-destructive";
    return notificationCenter
      ? `${baseClasses} right-[5.1rem] top-[5px]`
      : "hidden";
  };

  return (
    <div
      className={`flex h-[60px] w-full items-center justify-between border-b px-6 shadow-sm transition-all duration-200 dark:bg-background ${
        !isEmpty ? "hidden" : ""
      } hover:shadow-md`}
      data-testid="app-header"
    >
      {/* Left Section */}
      <div
        className={`z-30 flex items-center gap-4`}
        data-testid="header_left_section_wrapper"
      >
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="mr-2 flex h-10 w-10 items-center justify-center rounded-full transition-transform duration-200 hover:scale-110"
          data-testid="icon-ChevronLeft"
        >
          {ENABLE_DATASTAX_LANGFLOW ? (
            <DataStaxLogo className="fill-black dark:fill-[white]" />
          ) : (
            <img src={LangflowLogo} className="h-10 w-10" />
          )}
        </Button>
        {ENABLE_DATASTAX_LANGFLOW && (
          <div className="flex items-center gap-3">
            <CustomOrgSelector />
            <CustomProductSelector />
          </div>
        )}
        
      </div>

      {/* Middle Section */}
      <div className="w-full flex-1 truncate px-4 lg:absolute lg:left-1/2 lg:-translate-x-1/2">
        <FlowMenu />
      </div>

      {/* Right Section */}
      <div
        className={`relative left-3 z-30 flex items-center gap-3`}
        data-testid="header_right_section_wrapper"
      >
                
              
        <AlertDropdown
          notificationRef={notificationContentRef}
          onClose={() => setActiveState(null)}
        >
          <ShadTooltip
            content="Notifications and errors"
            side="bottom"
            styleClasses="z-10"
          >
            <AlertDropdown onClose={() => setActiveState(null)}>
              <Button
                ref={notificationRef}
                unstyled
                onClick={() =>
                  setActiveState((prev) =>
                    prev === "notifications" ? null : "notifications",
                  )
                }
                data-testid="notification_button"
                className="relative"
              >
                <div className="hit-area-hover group flex items-center rounded-full p-2 transition-colors duration-200 hover:bg-muted">
                  <span className={getNotificationBadge()} />
                  <ForwardedIconComponent
                    name="Bell"
                    className={`side-bar-button-size h-5 w-5 transition-colors duration-200 ${
                      activeState === "notifications"
                        ? "text-primary"
                        : "text-muted-foreground group-hover:text-primary"
                    }`}
                    strokeWidth={2}
                  />
                </div>
              </Button>
            </AlertDropdown>
          </ShadTooltip>
        </AlertDropdown>
        <Separator
          orientation="vertical"
          className="my-auto h-8 dark:border-zinc-700"
        />
        <div className="flex items-center gap-3 px-2 cursor-pointer" onClick={() => navigate("/settings")}>
          <div className="rounded-md bg-muted bg-success p-1.5">
            <ForwardedIconComponent name="Settings" className="h-4 w-4 text-foreground/70" />
          </div>
        </div>
        <Separator
          orientation="vertical"
          className="my-auto h-8 dark:border-zinc-700"
        />      
        <ThemeButtons />
        <Separator
          orientation="vertical"
          className="my-auto h-8 dark:border-zinc-700"
        /> 
        {/* <div className="flex items-center gap-3 px-2 cursor-pointer" onClick={handleLogout}>
          <div className="rounded-md bg-destructive/10 p-1.5">
            <ForwardedIconComponent name="LogOut" className="h-4 w-4 text-destructive" />
          </div>
        </div>
        <Separator
          orientation="vertical"
          className="my-auto h-8 dark:border-zinc-700"
        />  */}
        <div className="flex">
          <AccountMenu />
        </div>
      </div>
    </div>
  );
}
