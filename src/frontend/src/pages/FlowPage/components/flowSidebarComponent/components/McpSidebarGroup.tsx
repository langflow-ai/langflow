import { useState } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import { APIClassType } from "@/types/api";
import { removeCountFromString } from "@/utils/utils";
import { SearchConfigTrigger } from "./searchConfigTrigger";
import SidebarDraggableComponent from "./sidebarDraggableComponent";

type McpSidebarGroupProps = {
  mcpComponents?: any[];
  nodeColors: any;
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ) => void;
  openCategories: string[];
  setOpenCategories: React.Dispatch<React.SetStateAction<string[]>>;
  mcpServers?: any[];
  mcpLoading?: boolean;
  mcpSuccess?: boolean;
  mcpError?: boolean;
  search: string;
  hasMcpServers: boolean;
  showSearchConfigTrigger: boolean;
  showConfig: boolean;
  setShowConfig: React.Dispatch<React.SetStateAction<boolean>>;
};

const McpEmptyState = ({ isLoading }: { isLoading?: boolean }) => {
  const [addMcpOpen, setAddMcpOpen] = useState(false);

  const handleAddMcpServerClick = () => {
    setAddMcpOpen(true);
  };

  return (
    <>
      <div className="flex flex-col h-full w-full items-center justify-center py-8 px-4 text-center min-h-[200px]">
        <p className="text-muted-foreground mb-4">No MCP Servers Added</p>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading}
          onClick={handleAddMcpServerClick}
        >
          Add MCP Server
        </Button>
      </div>
      <AddMcpServerModal open={addMcpOpen} setOpen={setAddMcpOpen} />
    </>
  );
};

const McpSidebarGroup = ({
  mcpComponents,
  nodeColors,
  onDragStart,
  openCategories,
  setOpenCategories,
  mcpServers,
  mcpLoading,
  mcpSuccess,
  mcpError,
  search,
  hasMcpServers,
  showSearchConfigTrigger,
  showConfig,
  setShowConfig,
}: McpSidebarGroupProps) => {
  // Use props instead of hook call
  const isLoading = mcpLoading;
  const isSuccess = mcpSuccess;

  const categoryName = "MCP";
  const isOpen = search === "" || openCategories.includes(categoryName);

  // Only render if the MCP category is open (when not searching) or if we have search results
  if (!isOpen) {
    return null;
  }

  return (
    <SidebarGroup className={`p-3${!hasMcpServers ? " h-full" : ""}`}>
      {hasMcpServers && (
        <>
          <SidebarGroupLabel className="cursor-default">
            MCP Servers
          </SidebarGroupLabel>
          {showSearchConfigTrigger && (
            <SearchConfigTrigger
              showConfig={showConfig}
              setShowConfig={setShowConfig}
            />
          )}
        </>
      )}
      <SidebarGroupContent className="h-full">
        <SidebarMenu className={!hasMcpServers ? " h-full" : ""}>
          {isLoading && <span>Loading...</span>}
          {isSuccess && !hasMcpServers && (
            <McpEmptyState isLoading={isLoading} />
          )}
          {isSuccess &&
            mcpComponents &&
            hasMcpServers &&
            mcpComponents.map((mcpComponent, idx) => (
              <ShadTooltip
                content={mcpComponent.display_name || mcpComponent.name}
                side="right"
                key={idx}
              >
                <SidebarDraggableComponent
                  sectionName={"mcp"}
                  apiClass={mcpComponent}
                  icon={mcpComponent.icon ?? "Mcp"}
                  onDragStart={(event) =>
                    onDragStart(event, {
                      type: removeCountFromString("MCP"),
                      node: mcpComponent,
                    })
                  }
                  color={nodeColors["agents"]}
                  itemName={"MCP"}
                  error={!!mcpComponent.error}
                  display_name={
                    mcpComponent.mcpServerName ?? mcpComponent.display_name
                  }
                  official={mcpComponent.official === false ? false : true}
                  beta={mcpComponent.beta ?? false}
                  legacy={mcpComponent.legacy ?? false}
                  disabled={false}
                  disabledTooltip={""}
                />
              </ShadTooltip>
            ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

export default McpSidebarGroup;
