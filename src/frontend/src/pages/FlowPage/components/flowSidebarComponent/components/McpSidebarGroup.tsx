import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
} from "@/components/ui/sidebar";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { APIClassType } from "@/types/api";
import { removeCountFromString } from "@/utils/utils";
import SidebarDraggableComponent from "./sidebarDraggableComponent";
import SidebarItemsList from "./sidebarItemsList";

type McpSidebarGroupProps = {
  openCategories: string[];
  setOpenCategories;
  dataFilter: any;
  nodeColors: any;
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ) => void;
  sensitiveSort: (a: any, b: any) => number;
};

const McpSidebarGroup = ({
  dataFilter,
  nodeColors,
  onDragStart,
  sensitiveSort,
}) => {
  const {
    data: mcpServers,
    isLoading,
    isSuccess,
    isError,
  } = useGetMCPServers();

  console.log(mcpServers);

  const mcpComponent = dataFilter["agents"]["MCPTools"];

  console.log(mcpComponent);

  return (
    <SidebarGroup className="p-3">
      <SidebarGroupContent>
        <SidebarMenu>
          {isLoading && <span>Loading...</span>}
          {isSuccess &&
            mcpServers.map((mcpServer, idx) => (
              <ShadTooltip content={mcpServer.name} side="right" key={idx}>
                <SidebarDraggableComponent
                  sectionName={"mcp"}
                  apiClass={mcpComponent}
                  icon={mcpComponent.icon ?? "Unknown"}
                  onDragStart={(event) =>
                    onDragStart(event, {
                      type: removeCountFromString("MCP"),
                      node: mcpComponent,
                    })
                  }
                  color={nodeColors["agents"]}
                  itemName={"MCP"}
                  error={!!mcpComponent.error}
                  display_name={mcpServer.name}
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
