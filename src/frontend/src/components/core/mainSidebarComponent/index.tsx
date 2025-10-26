import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Home, Workflow, Package, Store, Play, ShoppingCart } from "lucide-react";
import { useSidebar } from "@/contexts/sidebarContext";
import ShadTooltip from "@/components/common/shadTooltipComponent";

interface SidebarItem {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  label: string;
}

const sidebarItems: SidebarItem[] = [
  { id: 'aistudio', icon: Home, path: '/agent-builder', label: 'AI Studio' },
  // { id: 'agentmarketplace', icon: Workflow, path: '/agent-marketplace', label: 'Agent Marketplace' },
  { id: 'marketplace', icon: Workflow, path: '/marketplace', label: 'Marketplace' },
  { id: 'integration', icon: Package, path: '/components', label: 'Integration' },
  { id: 'monitor', icon: Store, path: '/store', label: 'Monitor' },
];

export default function MainSidebar(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const { isCollapsed } = useSidebar();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div
      className={`
        flex h-full flex-col bg-white dark:bg-background border-r border-gray-200 dark:border-border shadow-sm transition-all duration-300 ease-in-out
        ${isCollapsed ? 'w-16' : 'w-60'}
      `}
    >
      <div className={`flex flex-col gap-1 py-4 ${isCollapsed ? 'items-center px-1.5' : 'px-3'}`}>
        {sidebarItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          const disabled = item.id === 'integration' || item.id === 'monitor';

          const buttonElement = (
            <button
              key={item.id}
              onClick={disabled ? undefined : () => navigate(item.path)}
              disabled={disabled}
              className={`
                flex items-center rounded-md transition-all duration-200
                ${isCollapsed
                  ? 'h-11 w-11 justify-center'
                  : 'h-12 w-full justify-start gap-3 px-3'
                }
                ${disabled
                  ? 'opacity-50 cursor-not-allowed'
                  : active
                    ? 'bg-[#E6E0F5] dark:bg-primary/10 text-[#350E84] dark:text-primary'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-accent hover:text-[#350E84] dark:hover:text-primary'
                }
              `}
            >
              <Icon
                className={`${
                  isCollapsed ? 'h-5 w-5' : 'h-5 w-5'
                } flex-shrink-0 ${active ? 'text-[#350E84] dark:text-white' : ''}`}
              />
              {!isCollapsed && (
                <span className="text-sm font-medium truncate">
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
    </div>
  );
}