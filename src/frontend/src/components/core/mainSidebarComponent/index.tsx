import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Home, Workflow, Package, Store, Play } from "lucide-react";
// Sidebar context has been removed

interface SidebarItem {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  label: string;
}

const sidebarItems: SidebarItem[] = [
  { id: 'aistudio', icon: Home, path: '/agent-builder', label: 'AI Studio' },
  { id: 'agentmarketplace', icon: Workflow, path: '/flows', label: 'Agent Marketplace' },
  { id: 'integration', icon: Package, path: '/components', label: 'Integration' },
  { id: 'monitor', icon: Store, path: '/store', label: 'Monitor' },
];

export default function MainSidebar(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const isCollapsed = false; // Sidebar is no longer collapsible

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div 
      className={`
        flex h-full flex-col bg-gray-50 border-r border-gray-200 shadow-sm transition-all duration-300 ease-in-out
        ${isCollapsed ? 'w-16' : 'w-60'}
      `}
    >
      <div className={`flex flex-col gap-3 py-6 ${isCollapsed ? 'items-center' : 'px-3'}`}>
        {sidebarItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.path)}
              className={`
                flex items-center rounded-lg transition-all duration-200
                ${isCollapsed 
                  ? 'h-12 w-12 justify-center' 
                  : 'h-10 w-full justify-start gap-3 px-3'
                }
                ${active 
                  ? 'bg-blue-100 text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }
              `}
              title={isCollapsed ? item.label : undefined}
            >
              <Icon className={`${isCollapsed ? 'h-6 w-6' : 'h-5 w-5'} flex-shrink-0`} />
              {!isCollapsed && (
                <span className="text-sm font-medium truncate">
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}