import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";
import { CustomLink } from "@/customization/components/custom-link";
import {
  ENABLE_LANGFLOW_STORE,
  ENABLE_NEW_SIDEBAR,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import AddMcpServerModal from "@/modals/addMcpServerModal";

const SidebarMenuButtons = ({
  hasStore = false,
  customComponent,
  addComponent,
  isLoading = false,
}) => {
  const { activeSection } = useSidebar();
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const navigate = useCustomNavigate();

  const handleAddMcpServerClick = () => {
    setAddMcpOpen(true);
  };

  return (
    <>
      {/* TODO: Remove this on cleanup */}
      {ENABLE_LANGFLOW_STORE && hasStore && (
        <SidebarMenuButton asChild>
          <CustomLink
            to="/store"
            target="_blank"
            rel="noopener noreferrer"
            className="group/discover"
          >
            <div className="flex w-full items-center gap-2">
              <ForwardedIconComponent
                name="Store"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="flex-1 group-data-[state=open]/collapsible:font-semibold">
                Discover more components
              </span>
              <ForwardedIconComponent
                name="SquareArrowOutUpRight"
                className="h-4 w-4 opacity-0 transition-all group-hover/discover:opacity-100"
              />
            </div>
          </CustomLink>
        </SidebarMenuButton>
      )}
      {ENABLE_NEW_SIDEBAR && activeSection === "mcp" ? (
        <>
          <SidebarMenuButton asChild>
            <Button
              unstyled
              disabled={isLoading}
              onClick={handleAddMcpServerClick}
              data-testid="sidebar-add-mcp-server-button"
              className="flex items-center gap-2"
            >
              <ForwardedIconComponent
                name="Plus"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="group-data-[state=open]/collapsible:font-semibold">
                Add MCP Server
              </span>
            </Button>
          </SidebarMenuButton>
          <SidebarMenuButton asChild>
            <Button
              unstyled
              disabled={isLoading}
              onClick={() => {
                navigate("/settings/mcp-servers");
              }}
              data-testid="sidebar-manage-servers-button"
              className="flex items-center gap-2"
            >
              <ForwardedIconComponent
                name="ArrowUpRight"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="group-data-[state=open]/collapsible:font-semibold">
                Manage Servers
              </span>
            </Button>
          </SidebarMenuButton>
          <AddMcpServerModal open={addMcpOpen} setOpen={setAddMcpOpen} />
        </>
      ) : (
        <SidebarMenuButton asChild>
          <Button
            unstyled
            disabled={isLoading}
            onClick={() => {
              if (customComponent) {
                addComponent(customComponent, "CustomComponent");
              }
            }}
            data-testid="sidebar-custom-component-button"
            className="flex items-center gap-2"
          >
            <ForwardedIconComponent
              name="Plus"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="group-data-[state=open]/collapsible:font-semibold">
              New Custom Component
            </span>
          </Button>
        </SidebarMenuButton>
      )}
    </>
  );
};

export default SidebarMenuButtons;
