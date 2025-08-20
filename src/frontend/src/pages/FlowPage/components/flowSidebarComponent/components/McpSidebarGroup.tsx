import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { APIClassType } from "@/types/api";
import { removeCountFromString } from "@/utils/utils";
import SidebarDraggableComponent from "./sidebarDraggableComponent";

type McpSidebarGroupProps = {
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
}: McpSidebarGroupProps) => {
  const {
    data: mcpServers,
    isLoading,
    isSuccess,
    isError,
  } = useGetMCPServers();

  const mcpComponent = dataFilter["agents"]["MCPTools"];

  const updatedMcpComponent = (mcpServer: any) => {
    const updatedMcpComponent = {
      ...mcpComponent,
      template: {
        ...mcpComponent.template,
        mcp_server: {
          ...mcpComponent.template.mcp_server,
          value: mcpServer,
        },
      },
    };

    return updatedMcpComponent;
  };

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
                      node: updatedMcpComponent(mcpServer),
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
