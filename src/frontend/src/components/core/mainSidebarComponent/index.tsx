import React, { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  Workflow,
  Package,
  Store,
  Play,
  FolderCode,
  PanelLeftOpen,
  PanelLeftClose,
  ClipboardList,
} from "lucide-react";
import { useSidebar } from "@/contexts/sidebarContext";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { envConfig } from "@/config/env";
import useAuthStore from "@/stores/authStore";
import { USER_ROLES } from "@/types/auth";
import { AiStudioIcon } from "@/assets/icons/AiStudioIcon";
import { MarketplaceIcon } from "@/assets/icons/MarketplaceIcon";
import { IntegrationIcon } from "@/assets/icons/IntegrationIcon";
import { MonitorIcon } from "@/assets/icons/MonitorIcon";
import { ExpandIcon } from "@/assets/icons/ExpandIcon";
import { Button } from "@/components/ui/button";

interface SidebarItem {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  label: string;
  external?: boolean;
  requiredRoles?: string[]; // Roles required to see this menu item
}

const sidebarItems: SidebarItem[] = [
  {
    id: "aistudio",
    icon: AiStudioIcon,
    path: "/agent-builder",
    label: "AI Studio",
  },
  // { id: 'agentmarketplace', icon: Workflow, path: '/agent-marketplace', label: 'Agent Marketplace' },
  {
    id: "marketplace",
    icon: MarketplaceIcon,
    path: "/marketplace",
    label: "Agent Marketplace",
  },
  {
    id: "integration",
    icon: IntegrationIcon,
    path: "/components",
    label: "Integration",
  },
  { id: "monitor", icon: MonitorIcon, path: "/store", label: "Monitor" },
  {
    id: "prompt-management",
    icon: FolderCode,
    path: envConfig.promptsUrl ?? "prompt-management",
    label: "Prompts",
    external: true,
  },
  {
    id: "all-requests",
    icon: ClipboardList,
    path: "/all-requests",
    label: "All Requests",
    requiredRoles: [USER_ROLES.MARKETPLACE_ADMIN],
  },
];

export default function MainSidebar(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const { isCollapsed, toggleSidebar } = useSidebar();
  const userRoles = useAuthStore((state) => state.userRoles);

  // Filter sidebar items based on user roles
  const visibleSidebarItems = useMemo(() => {
    return sidebarItems.filter((item) => {
      // If no required roles, show to everyone
      if (!item.requiredRoles || item.requiredRoles.length === 0) {
        return true;
      }
      // Check if user has any of the required roles
      return item.requiredRoles.some((role) => userRoles.includes(role));
    });
  }, [userRoles]);

  const isActive = (path: string) => {
    if (path === "/") {
      return location.pathname === "/";
    }
    return location.pathname.startsWith(path);
  };

  const handleNavigate = (path: string, external?: boolean) => {
    if (external) {
      if (!path) return;
      window.open(path, "_blank");
    } else {
      navigate(path);
    }
  };

  return (
    <div
      className={`flex h-full flex-col bg-background-surface z-[1] shadow-[0_1px_8px_0_rgba(var(--boxshadow),0.1)] transition-all duration-300 ease-in-out
          ${isCollapsed ? "w-14" : "w-[192px]"}
        `}
    >
      <div
        className={`flex flex-col gap-2 py-4 px-3 ${
          isCollapsed ? "items-center px-1.5" : "px-3"
        }`}
      >
        {visibleSidebarItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          const disabled = item.id === "integration" || item.id === "monitor";

          const buttonElement = (
            <button
              key={item.id}
              onClick={
                disabled
                  ? undefined
                  : () => handleNavigate(item.path, item?.external)
              }
              disabled={disabled}
              className={`
              flex items-center rounded-md transition-all duration-200
              ${
                isCollapsed
                  ? "h-8 w-8 justify-center"
                  : "h-8 w-full justify-start gap-3 px-2"
              }
              ${
                disabled
                  ? "opacity-30 cursor-not-allowed"
                  : active
                  ? "bg-accent text-menu"
                  : "text-secondary-font hover:bg-accent hover:text-menu"
              }
              `}
            >
              <Icon
                className={`h-3.5 w-4 flex-shrink-0 ${
                  active ? "text-menu" : "hover:text-menu"
                }`}
              />
              {!isCollapsed && (
                <span
                  className={`text-sm truncate ${
                    active ? "font-medium" : "font-normal"
                  }`}
                >
                  {item.label}
                </span>
              )}
            </button>
          );

          if (isCollapsed) {
            return (
              <ShadTooltip key={item.id} content={item.label} side="right">
                {buttonElement}
              </ShadTooltip>
            );
          }

          return buttonElement;
        })}
      </div>

      {/* Bottom Toggle */}
      <div className={`mt-auto p-3 items-center`}>
        <ShadTooltip content="Expand sidebar" side="right">
          <button
            onClick={toggleSidebar}
            className={`px-2 flex items-center rounded-md transition-all duration-200 text-secondary-font hover:bg-accent hover:text-menu ${
              isCollapsed
                ? "h-8 w-8 justify-center"
                : "h-8 w-full justify-start"
            }`}
            data-testid="main-sidebar-toggle"
          >
            {isCollapsed ? (
              <ExpandIcon />
            ) : (
              <ExpandIcon className="rotate-180" />
            )}
          </button>
        </ShadTooltip>
        {/* {isCollapsed ? (
          <ShadTooltip content="Expand sidebar" side="right">
            <button
              onClick={toggleSidebar}
              className="h-8 w-8 flex items-center justify-center rounded-md text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-accent hover:text-primary dark:hover:text-primary"
              data-testid="main-sidebar-toggle"
            >
              <ExpandIcon />
            </button>
          </ShadTooltip>
        ) : (
          <button
            onClick={toggleSidebar}
            className="h-8 w-full flex items-center justify-start gap-3 px-3 rounded-md text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-accent hover:text-primary dark:hover:text-primary"
            data-testid="main-sidebar-toggle"
          >
            <PanelLeftClose className="h-5 w-5 flex-shrink-0" />
          </button>
        )} */}
      </div>
    </div>
  );
}
