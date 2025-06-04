import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDeleteMCPServer } from "@/controllers/API/queries/mcp/use-delete-mcp-server";
import { useGetMCPServer } from "@/controllers/API/queries/mcp/use-get-mcp-server";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import useAlertStore from "@/stores/alertStore";
import { MCPServerInfoType } from "@/types/mcp";
import { useState } from "react";

export default function MCPServersPage() {
  const { data: servers = [], refetch } = useGetMCPServers();
  const { mutate: deleteServer } = useDeleteMCPServer();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editInitialData, setEditInitialData] = useState<any>(null);
  const [loadingEdit, setLoadingEdit] = useState(false);
  const { mutateAsync: getServer } = useGetMCPServer();

  const handleEdit = async (name: string) => {
    setLoadingEdit(true);
    try {
      const data = await getServer({ name });
      setEditInitialData(data);
      setEditOpen(true);
    } catch (e: any) {
      setErrorData({ title: "Error fetching server", list: [e.message] });
    } finally {
      setLoadingEdit(false);
    }
  };

  const handleDelete = (server: MCPServerInfoType) => {
    deleteServer(
      { name: server.name },
      {
        onSuccess: () => refetch(),
        onError: (e: any) =>
          setErrorData({ title: "Error deleting server", list: [e.message] }),
      },
    );
  };

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-center justify-between gap-6">
        <div className="flex flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            MCP Servers
            <ForwardedIconComponent
              name="Mcp"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage MCP Servers for use in your flows.
          </p>
        </div>
        <Button variant="primary" onClick={() => setAddOpen(true)}>
          <ForwardedIconComponent name="Plus" className="w-4" />
          Add MCP Server
        </Button>
        <AddMcpServerModal open={addOpen} setOpen={setAddOpen} />
      </div>
      <div className="flex flex-col gap-2">
        {servers.length === 0 && (
          <div className="text-sm text-muted-foreground">
            No MCP servers found.
          </div>
        )}
        {servers.map((server) => (
          <div
            key={server.id}
            className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3 shadow-sm transition-colors hover:bg-accent"
          >
            <div className="flex items-center gap-3">
              <ForwardedIconComponent
                name="Mcp"
                className="h-6 w-6 text-primary"
              />
              <div className="flex flex-col">
                <span className="text-base font-medium">{server.name}</span>
                <span className="text-xs text-muted-foreground">
                  {server.toolsCount} action{server.toolsCount === 1 ? "" : "s"}
                </span>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="iconSm"
                  className="hover:bg-accent"
                >
                  <ForwardedIconComponent
                    name="EllipsisVertical"
                    className="h-5 w-5"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleEdit(server.name)}>
                  <ForwardedIconComponent
                    name="SquarePen"
                    className="mr-2 h-4 w-4"
                  />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => handleDelete(server)}
                  className="text-destructive"
                >
                  <ForwardedIconComponent
                    name="Trash2"
                    className="mr-2 h-4 w-4"
                  />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ))}
        {editOpen && (
          <AddMcpServerModal
            open={editOpen}
            setOpen={setEditOpen}
            initialData={editInitialData}
          />
        )}
      </div>
    </div>
  );
}
