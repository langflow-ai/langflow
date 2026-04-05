import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import { useUtilityStore } from "@/stores/utilityStore";

const SidebarMenuButtons = ({
  customComponent,
  addComponent,
  isLoading = false,
}) => {
  const { activeSection } = useSidebar();
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const navigate = useCustomNavigate();
  const allowCustomComponents = useUtilityStore(
    (state) => state.allowCustomComponents,
  );

  const handleAddMcpServerClick = () => {
    setAddMcpOpen(true);
  };

  // Hide custom component button when custom components are blocked
  if (
    !allowCustomComponents &&
    !(ENABLE_NEW_SIDEBAR && activeSection === "mcp")
  ) {
    return null;
  }

  return ENABLE_NEW_SIDEBAR && activeSection === "mcp" ? (
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
  ) : (
    <SidebarMenuButton asChild className="group">
      <Button
        unstyled
        disabled={isLoading}
        onClick={() => {
          if (customComponent) {
            addComponent(customComponent, "CustomComponent");
          }
        }}
        data-testid="sidebar-custom-component-button"
        className="flex items-center w-full h-full gap-3 hover:bg-muted"
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
  );
};

export default SidebarMenuButtons;
