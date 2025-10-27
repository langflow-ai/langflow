import { useEffect, useRef, useState } from "react";
import AlertDropdown from "@/alerts/alertDropDown";
import DataStaxLogo from "@/assets/DataStaxLogo.svg?react";
// import AutonomizeLogoUrl from "@/assets/autonomize-full-logo.png";
import AutonomizeLogoUrl from "@/assets/autonomize-poweredby-logo.png";
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
import useLogoStore from "@/stores/logoStore";
import { useSidebar } from "@/contexts/sidebarContext";
import { PanelLeft, Moon, Sun } from "lucide-react";
import FlowMenu from "./components/FlowMenu";
import Breadcrumb from "@/components/common/Breadcrumb";
import { useLocation } from "react-router-dom";
import { useDarkStore } from "@/stores/darkStore";
import { useGetAppConfig } from "@/controllers/API/queries/application-config";
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
  const customLogoUrl = useLogoStore((state) => state.logoUrl);
  const setLogoUrl = useLogoStore((state) => state.setLogoUrl);
  useTheme();
  const location = useLocation();

  // Load logo from database on mount
  const { data: logoConfig } = useGetAppConfig(
    { key: "app-logo" },
    {
      retry: false,
      refetchOnWindowFocus: false,
      onError: () => {
        // Silently ignore if logo config doesn't exist
      },
    }
  );

  // Update logo store when logo config is loaded from database
  useEffect(() => {
    if (logoConfig?.value) {
      setLogoUrl(logoConfig.value);
    }
  }, [logoConfig, setLogoUrl]);

  const toggleTheme = () => {
    const newDark = !dark;
    setDark(newDark);
    try {
      localStorage.setItem("themePreference", newDark ? "dark" : "light");
    } catch {
      // ignore storage errors
    }
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

  // Breadcrumb navigation (route-aware)
  const breadcrumbItems = (() => {
    const pathname = location.pathname || "";
    const state = location.state as { name?: string; fileName?: string } | undefined;

    // AI Studio (builder) hierarchy
    // if (pathname.startsWith("/agent-builder")) {
    //   return [{ label: "AI Studio", href: "/agent-builder" }];
    // }

    // Agent Marketplace hierarchy
    if (pathname.startsWith("/agent-marketplace")) {
      const items = [{ label: "Agent Marketplace", href: "/agent-marketplace" }];
      if (pathname.startsWith("/agent-marketplace/detail")) {
        const current = state?.name || state?.fileName || "Details";
        items.push({ label: current, href: '' });
      }
      return items;
    }

    // Default: no breadcrumbs beyond logo
    return [];
  })();

  return (
    <div
      className={`z-10 flex h-[48px] w-full items-center justify-between border-b pr-5 pl-2.5`}
      style={{ backgroundColor: "#350E84" }}
      data-testid="app-header"
    >
      {/* Left Section */}
      <div
        className={`z-30 flex shrink-0 items-center gap-7`}
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
        <div className="flex items-center gap-2">
          {/* Custom Logo - appears before Autonomize logo when uploaded */}
          {customLogoUrl && !ENABLE_DATASTAX_LANGFLOW && (
            <Button
              unstyled
              onClick={() => navigate("/")}
              className="flex h-8 w-24 items-center"
              data-testid="custom-logo-button"
            >
              <img
                src={customLogoUrl}
                alt="Custom Logo"
                className="h-full w-full object-contain"
              />
            </Button>
          )}

        </div>
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
                  {/* Autonomize Logo - always visible */}
          <Button
            unstyled
            onClick={() => navigate("/")}
            className="mr-1 flex h-8 w-24 items-center"
            data-testid="icon-ChevronLeft"
          >
            {ENABLE_DATASTAX_LANGFLOW ? (
              <DataStaxLogo className="fill-black dark:fill-[white]" />
            ) : (
              <img
                src={AutonomizeLogoUrl}
                alt="Autonomize Logo"
                className="h-full w-full object-contain"
              />
            )}
          </Button>
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
