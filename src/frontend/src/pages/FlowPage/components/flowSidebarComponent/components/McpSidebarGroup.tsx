import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { APIClassType } from "@/types/api";
import { removeCountFromString } from "@/utils/utils";
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
}: McpSidebarGroupProps) => {
  // Use props instead of hook call
  const isLoading = mcpLoading;
  const isSuccess = mcpSuccess;

  const categoryName = "MCP";
  const isOpen = openCategories.includes(categoryName);

  // Only render if the MCP category is open (when not searching) or if we have search results
  if (!isOpen && search === "") {
    return null;
  }

  return (
    <SidebarGroup className="p-3">
      <SidebarGroupLabel className="cursor-default">
        MCP Servers
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {isLoading && <span>Loading...</span>}
          {isSuccess &&
            mcpComponents &&
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
                  display_name={mcpComponent.display_name}
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
