import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";
import {
  ENABLE_NEW_SIDEBAR,
  LANGFLOW_AGENTIC_EXPERIENCE,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import { useForgeStore } from "@/stores/forgeStore";
import { useGetForgeConfig } from "@/controllers/API/queries/forge";
import useAlertStore from "@/stores/alertStore";

const SidebarMenuButtons = ({
  customComponent,
  addComponent,
  isLoading = false,
}) => {
  const { activeSection } = useSidebar();
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const navigate = useCustomNavigate();
  const toggleTerminal = useForgeStore((state) => state.toggleTerminal);
  const { data: forgeConfigData } = useGetForgeConfig();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const isForgeConfigured = forgeConfigData?.configured ?? false;

  const handleAddMcpServerClick = () => {
    setAddMcpOpen(true);
  };

  const handleForgeClick = () => {
    if (!isForgeConfigured) {
      setErrorData({
        title: "Component Forge requires configuration",
        list: [
          "ANTHROPIC_API_KEY is required to use Component Forge.",
          "Please add it to your environment variables or configure it in Settings > Global Variables.",
        ],
      });
      return;
    }
    toggleTerminal();
  };

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
    <>
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
      {LANGFLOW_AGENTIC_EXPERIENCE && (
        <SidebarMenuButton asChild className="group">
          <Button
            unstyled
            disabled={isLoading}
            onClick={handleForgeClick}
            data-testid="sidebar-component-forge-button"
            className="flex items-center w-full h-full gap-3 hover:bg-muted"
          >
            <ForwardedIconComponent
              name="Sparkles"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="group-data-[state=open]/collapsible:font-semibold">
              Component Forge
            </span>
          </Button>
        </SidebarMenuButton>
      )}
    </>
  );
};

export default SidebarMenuButtons;
