import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
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
        <div className="flex flex-col w-full h-full">
          <Button
            unstyled
            disabled={isLoading}
            onClick={handleAddMcpServerClick}
            data-testid="sidebar-add-mcp-server-button"
            className="flex items-center gap-2 p-3 hover:bg-muted"
          >
            <ForwardedIconComponent
              name="Plus"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="text-sm">Add MCP Server</span>
          </Button>

          <Button
            unstyled
            disabled={isLoading}
            onClick={() => {
              navigate("/settings/mcp-servers");
            }}
            data-testid="sidebar-manage-servers-button"
            className="flex items-center gap-2 p-3 hover:bg-muted"
          >
            <ForwardedIconComponent
              name="ArrowUpRight"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="text-sm">Manage Servers</span>
          </Button>
          <AddMcpServerModal open={addMcpOpen} setOpen={setAddMcpOpen} />
        </div>
      ) : (
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
          <span className="ml-2group-data-[state=open]/collapsible:font-semibold text-sm">
            New Custom Component
          </span>
        </Button>
      )}
    </div>
  );
};

export default SidebarMenuButtons;
