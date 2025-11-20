import { useEffect, useRef, useState } from "react";
import AlertDropdown from "@/alerts/alertDropDown";
import DataStaxLogo from "@/assets/DataStaxLogo.svg?react";
import AutonomizeShortLogo from "@/assets/Vector.png";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import CustomAccountMenu from "@/customization/components/custom-AccountMenu";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { CustomProductSelector } from "@/customization/components/custom-product-selector";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { ENABLE_CUSTOM_PARAM } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import useLogoStore from "@/stores/logoStore";
import { Moon, Sun } from "lucide-react";
import FlowMenu from "./components/FlowMenu";
import Breadcrumb from "@/components/common/Breadcrumb";
import { useLocation } from "react-router-dom";
import { useDarkStore } from "@/stores/darkStore";
import { useGetAppConfig } from "@/controllers/API/queries/application-config";
import { useGetPublishedFlow, useCheckFlowPublished } from "@/controllers/API/queries/published-flows";
import { useGetAgentByFlowId } from "@/controllers/API/queries/agent-marketplace/use-get-agent-by-flow-id";
import { AppLogoDisplay } from "@/components/AppLogoDisplay";
import useFlowStore from "@/stores/flowStore";
// import AutonomizeIcon from "@/icons/Autonomize";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  const [activeState, setActiveState] = useState<"notifications" | null>(null);
  const notificationRef = useRef<HTMLButtonElement | null>(null);
  const notificationContentRef = useRef<HTMLDivElement | null>(null);
  const dark = useDarkStore((state) => state.dark);
  const setDark = useDarkStore((state) => state.setDark);
  const customLogoUrl = useLogoStore((state) => state.logoUrl);
  const setLogoUrl = useLogoStore((state) => state.setLogoUrl);
  useTheme();
  const location = useLocation();
  const currentFlowName = useFlowStore((state) => state.currentFlow?.name);

  // Path parsing for route-aware data fetching
  const pathname = location.pathname || "";
  const state = location.state as { name?: string; fileName?: string } | undefined;
  const rawSegments = pathname.split("/").filter(Boolean);
  const segments = [...rawSegments];
  if (ENABLE_CUSTOM_PARAM && segments.length > 0) {
    // Remove leading custom param if present
    segments.shift();
  }
  const head = segments[0];
  const tail = segments.slice(1);
  const agentFlowId = head === "agent-marketplace" && tail[0] === "detail" ? tail[1] : undefined;
  const publishedFlowId = head === "marketplace" && tail[0] === "detail" ? tail[1] : undefined;
  const flowId = head === "flow" && tail[0] ? tail[0] : undefined;

  // Fetch names for detail pages (disabled unless route matches)
  const { data: agentData } = useGetAgentByFlowId(
    { flow_id: agentFlowId || "" },
    { enabled: !!agentFlowId && agentFlowId !== "no-flow", refetchOnWindowFocus: false }
  );
  const { data: publishedFlowData } = useGetPublishedFlow(publishedFlowId);

  // Check if current flow is published (to show marketplace name in breadcrumb)
  const { data: currentFlowPublishedData } = useCheckFlowPublished(flowId);

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
    } else if (logoConfig && !logoConfig.value) {
      // Handle empty logo value (logo removed)
      setLogoUrl(null);
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
    if (segments.length === 0) return [];

    // Helpers
    const detailLabel = state?.name || state?.fileName || "Details";
    const items: { label: string; href?: string; beta?: boolean }[] = [];

    switch (head) {
      case "agent-builder": {
        items.push({ label: "AI Studio", href: "/agent-builder" });
        if (tail[0] === "conversation" && tail[1]) {
          items.push({ label: "Conversation" });
        }
        break;
      }
      case "agent-marketplace": {
        // Prepend AI Studio before Agent Marketplace
        items.push({ label: "AI Studio", href: "/agent-builder" });
        items.push({ label: "Agent Marketplace", href: "/agent-marketplace" });
        if (tail[0] === "detail") {
          const agentName = agentData?.spec?.name;
          items.push({ label: agentName || detailLabel });
        }
        break;
      }
      case "marketplace": {
        // Prepend AI Studio before Marketplace
        items.push({ label: "AI Studio", href: "/agent-builder" });
        items.push({ label: "Marketplace", href: "/marketplace" });
        if (tail[0] === "detail") {
          const publishedName = publishedFlowData?.flow_name;
          items.push({ label: publishedName || detailLabel });
        }
        break;
      }
      case "flows": {
        items.push({ label: "Flows", href: "/flows" });
        if (tail[0] === "folder" && tail[1]) {
          items.push({ label: "Folder" });
        }
        break;
      }
      case "components": {
        items.push({ label: "Components", href: "/components" });
        if (tail[0] === "folder" && tail[1]) {
          items.push({ label: "Folder" });
        }
        break;
      }
      case "all": {
        items.push({ label: "All", href: "/all" });
        if (tail[0] === "folder" && tail[1]) {
          items.push({ label: "Folder" });
        }
        break;
      }
      case "mcp": {
        items.push({ label: "MCP", href: "/mcp" });
        if (tail[0] === "folder" && tail[1]) {
          items.push({ label: "Folder" });
        }
        break;
      }
      case "flow": {
        // Show AI Studio and the current flow name (if available)
        items.push({ label: "AI Studio", href: "/agent-builder" });
        // If flow is published, show marketplace name. Otherwise, show actual flow name.
        const displayName = currentFlowName || detailLabel;
        items.push({ label: displayName });
        break;
      }
      case "settings": {
        items.push({ label: "Settings", href: "/settings" });
        const sub = tail[0];
        if (sub) {
          const labelMap: Record<string, string> = {
            "general": "General",
            "api-keys": "API Keys",
            "global-variables": "Global Variables",
            "mcp-servers": "MCP Servers",
            "shortcuts": "Shortcuts",
            "messages": "Messages",
            "store": "Store",
          };
          items.push({ label: labelMap[sub] ?? sub });
        }
        break;
      }
      case "store": {
        items.push({ label: "Store", href: "/store" });
        if (tail[0]) {
          items.push({ label: "Details" });
        }
        break;
      }
      case "playground": {
        items.push({ label: "Playground" });
        break;
      }
      case "account": {
        items.push({ label: "Account", href: "/account" });
        if (tail[0] === "delete") {
          items.push({ label: "Delete" });
        }
        break;
      }
      case "admin": {
        items.push({ label: "Admin" });
        break;
      }
      case "assets": {
        items.push({ label: "Assets", href: "/assets" });
        if (tail[0] === "files") items.push({ label: "Files" });
        if (tail[0] === "knowledge-bases") items.push({ label: "Knowledge Bases" });
        break;
      }
      default: {
        // Unrecognized path: no breadcrumbs beyond logo
        break;
      }
    }

    return items;
  })();

  return (
    <div
      className={`z-10 flex h-[48px] w-full items-center justify-between border-b pr-5 pl-2.5`}
      style={{ backgroundColor: "#350E84" }}
      data-testid="app-header"
    >
      {/* Left Section */}
      <div
        className={`z-30 flex shrink-0 items-center mr-2`}
        data-testid="header_left_section_wrapper"
      >
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="flex h-8 items-center"
          data-testid="icon-ChevronLeft"
        >
          {ENABLE_DATASTAX_LANGFLOW ? (
            <DataStaxLogo className="fill-black dark:fill-[white]" />
          ) : (
            <img
              src={AutonomizeShortLogo}
              alt="Autonomize Logo"
              className="p-3 object-contain"
            />
          )}
        </Button>
        {/* Vertical separator right after the logo */}
        <Separator orientation="vertical" className="!h-12 mx-1.5 opacity-50" />
        <div className="text-white text-[12px]">
          <Breadcrumb items={breadcrumbItems} className="my-8 mx-4" />
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
      <div className="flex items-center gap-2 md:gap-3">
        {/* Custom Logo - positioned left of theme toggle */}
        {customLogoUrl && !ENABLE_DATASTAX_LANGFLOW && (
          <Button
            unstyled
            onClick={() => navigate("/")}
            className="flex h-8 w-24 items-center"
            data-testid="custom-logo-button"
          >
            <AppLogoDisplay
              blobPath={customLogoUrl}
              className="h-full w-full object-contain"
            />
          </Button>
        )}
        {/* Theme Toggle Button */}
        <ShadTooltip content={dark ? "Switch to Light Mode" : "Switch to Dark Mode"}>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            className="h-8 w-8 p-0 text-white hover:bg-white/10"
            aria-label={dark ? "Switch to Light Mode" : "Switch to Dark Mode"}
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
