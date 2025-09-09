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

  return (
    <div className="flex w-full h-full">
      {ENABLE_NEW_SIDEBAR && activeSection === "mcp" ? (
        <>
          <SidebarMenuButton asChild>
            <Button
              unstyled
              disabled={isLoading}
              onClick={handleAddMcpServerClick}
              data-testid="sidebar-add-mcp-server-button"
              className="flex items-center gap-2 w-full p-0"
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
        // <SidebarMenuButton asChild className="group">
        <Button
          unstyled
          disabled={isLoading}
          onClick={() => {
            if (customComponent) {
              addComponent(customComponent, "CustomComponent");
            }
          }}
          data-testid="sidebar-custom-component-button"
          className="flex items-center w-full h-full p-3 gap-2 hover:bg-muted"
        >
          <ForwardedIconComponent
            name="Plus"
            className="h-4 w-4 text-muted-foreground"
          />
          <span className="ml-2 group-data-[state=open]/collapsible:font-semibold text-sm">
            New Custom Component
          </span>
        </Button>
        // </SidebarMenuButton>
      )}
    </div>
  );
};

export default SidebarMenuButtons;
