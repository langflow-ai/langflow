import { useEffect, useRef, useState } from "react";
import AlertDropdown from "@/alerts/alertDropDown";
import DataStaxLogo from "@/assets/DataStaxLogo.svg?react";
import AutonomizeLogoUrl from "@/assets/autonomize-full-logo.png";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import CustomAccountMenu from "@/customization/components/custom-AccountMenu";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { CustomProductSelector } from "@/customization/components/custom-product-selector";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import { useSidebar } from "@/contexts/sidebarContext";
import { PanelLeft, Moon, Sun } from "lucide-react";
import FlowMenu from "./components/FlowMenu";
import Breadcrumb from "@/components/common/Breadcrumb";
import { useDarkStore } from "@/stores/darkStore";
// import AutonomizeIcon from "@/icons/Autonomize";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  const [activeState, setActiveState] = useState<"notifications" | null>(null);
  const notificationRef = useRef<HTMLButtonElement | null>(null);
  const notificationContentRef = useRef<HTMLDivElement | null>(null);
  const { toggleSidebar } = useSidebar();
  const dark = useDarkStore((state) => state.dark);
  const setDark = useDarkStore((state) => state.setDark);
  useTheme();

  const toggleTheme = () => {
    setDark(!dark);
  };

  // useEffect(() => {
  //   function handleClickOutside(event: MouseEvent) {
  //     const target = event.target as Node;
  //     const isNotificationButton = notificationRef.current?.contains(target);
  //     const isNotificationContent =
  //       notificationContentRef.current?.contains(target);

  //     if (!isNotificationButton && !isNotificationContent) {
  //       setActiveState(null);
  //     }
  //   }

  //   document.addEventListener("mousedown", handleClickOutside);
  //   return () => {
  //     document.removeEventListener("mousedown", handleClickOutside);
  //   };
  // }, []);

  // const getNotificationBadge = () => {
  //   const baseClasses = "absolute h-1 w-1 rounded-full bg-destructive";
  //   return notificationCenter
  //     ? `${baseClasses} right-[0.3rem] top-[5px]`
  //     : "hidden";
  // };

  // Breadcrumb navigation
  const breadcrumbItems = [
    { label: "/" },
    { label: "AI Studio", href: "/agent-builder" },
  ];

  return (
    <div
      className={`z-10 flex h-[48px] w-full items-center justify-between border-b pr-5 pl-2.5`}
      style={{ backgroundColor: "#350E84" }}
      data-testid="app-header"
    >
      {/* Left Section */}
      <div
        className={`z-30 flex shrink-0 items-center gap-2`}
        data-testid="header_left_section_wrapper"
      >
        <ShadTooltip content="Toggle Sidebar">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className="h-8 w-8 p-0 text-white hover:bg-white/10"
            data-testid="sidebar-toggle-button"
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
        </ShadTooltip>
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="mr-1 flex h-8 w-24 items-center"
          data-testid="icon-ChevronLeft"
        >
          {ENABLE_DATASTAX_LANGFLOW ? (
            <DataStaxLogo className="fill-black dark:fill-[white]" />
          ) : (
            <img src={AutonomizeLogoUrl} alt="Autonomize Logo" />
          )}
        </Button>
        <div className="text-white text-[12px] font-medium mt-2">
          <Breadcrumb items={breadcrumbItems} className="mb-6 text-white font-medium mt-2" />
        </div>
        {ENABLE_DATASTAX_LANGFLOW && (
          <>
            <CustomOrgSelector />
            <CustomProductSelector />
          </>
        )}
      </div>

      {/* Middle Section */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <FlowMenu />
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-2">
        {/* Theme Toggle Button */}
        <ShadTooltip content={dark ? "Switch to Light Mode" : "Switch to Dark Mode"}>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            className="h-8 w-8 p-0 text-white hover:bg-white/10"
            data-testid="theme-toggle-button"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </ShadTooltip>

        {/* Account Menu */}
        <CustomAccountMenu />
      </div>
    </div>
  );
}
