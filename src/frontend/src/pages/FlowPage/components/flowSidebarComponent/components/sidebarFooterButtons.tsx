import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import AddMcpServerModal from "@/modals/addMcpServerModal";

const SidebarMenuButtons = ({
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

  if (ENABLE_NEW_SIDEBAR && activeSection === "mcp") {
    return (
      <>
        <SidebarMenuButton asChild>
          <Button
            unstyled
            disabled={isLoading}
            onClick={handleAddMcpServerClick}
            data-testid="sidebar-add-mcp-server-button"
            className="flex items-center w-full h-full gap-3 hover:bg-muted"
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
            className="flex items-center w-full h-full gap-3 hover:bg-muted"
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
    );
  }

  return null;
};

export default SidebarMenuButtons;
