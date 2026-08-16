import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Loading from "@/components/ui/loading";
import { useDeleteMCPServer } from "@/controllers/API/queries/mcp/use-delete-mcp-server";
import { useGetMCPServer } from "@/controllers/API/queries/mcp/use-get-mcp-server";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import type { MCPServerInfoType } from "@/types/mcp";
import { cn } from "@/utils/utils";

export default function MCPServersPage() {
  const { t } = useTranslation();
  const { data: servers } = useGetMCPServers({ withCounts: true });
  const { mutate: deleteServer } = useDeleteMCPServer();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const [editInitialData, setEditInitialData] = useState<any>(null);
  const { mutateAsync: getServer } = useGetMCPServer();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [serverToDelete, setServerToDelete] =
    useState<MCPServerInfoType | null>(null);

  const handleEdit = async (name: string) => {
    try {
      const data = await getServer({ name });
      setEditInitialData(data);
      setEditOpen(true);
      // biome-ignore lint/suspicious/noExplicitAny: legacy
    } catch (e: any) {
      setErrorData({
        title: t("mcp.servers.errorFetching"),
        list: [e.message],
      });
    } finally {
    }
  };

  const handleDelete = (server: MCPServerInfoType) => {
    deleteServer(
      { name: server.name },
      {
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        onError: (e: any) =>
          setErrorData({
            title: t("mcp.servers.errorDeleting"),
            list: [e.message],
          }),
      },
    );
  };

  const openDeleteModal = (server: MCPServerInfoType) => {
    setServerToDelete(server);
    setDeleteModalOpen(true);
  };

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("mcp.servers.title")}
            <ForwardedIconComponent
              name="Mcp"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("mcp.servers.description")}
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <Button
            variant="primary"
            onClick={() => setAddOpen(true)}
            data-testid="add-mcp-server-button-page"
          >
            <ForwardedIconComponent name="Plus" className="w-4" />
            <span>{t("mcp.servers.addButton")}</span>
          </Button>
          <AddMcpServerModal open={addOpen} setOpen={setAddOpen} />
        </div>
      </div>
      <div className="flex h-full flex-col gap-2">
        {servers ? (
          <>
            {servers.length === 0 && (
              <div className="w-full pt-8 text-center text-sm text-muted-foreground">
                {t("mcp.servers.noServersAdded")}
              </div>
            )}
            {servers.length > 0 && (
              <div
                id="mcp-servers-list-label"
                className="text-sm font-medium text-muted-foreground"
              >
                {t("mcp.servers.addedServers")}
              </div>
            )}
            {/* Rendered only when populated: a list role owning no listitem
                is an invalid ARIA parent (IBM aria_child_valid). */}
            {servers.length > 0 && (
              <ul
                aria-labelledby="mcp-servers-list-label"
                className="flex list-none flex-col gap-1 p-0"
              >
                {servers.map((server, index) => (
                  <li
                    key={server.name}
                    className="flex items-center justify-between rounded-lg px-3 py-2 shadow-sm transition-colors hover:bg-accent"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="text-sm font-medium"
                        data-testid={"mcp_server_name_" + index}
                      >
                        {server.name}
                      </span>
                      <ShadTooltip content={server.error}>
                        <span
                          className={cn(
                            "cursor-default select-none !text-mmd text-muted-foreground",
                            server.error && "text-accent-red-foreground",
                          )}
                        >
                          {server.toolsCount === null
                            ? server.error
                              ? server.error.startsWith("Timeout")
                                ? t("mcp.servers.statusTimeout")
                                : t("mcp.servers.statusError")
                              : t("mcp.servers.statusLoading")
                            : !server.toolsCount
                              ? t("mcp.servers.statusNoTools")
                              : t("mcp.servers.toolsCount", {
                                  count: server.toolsCount,
                                })}
                        </span>
                      </ShadTooltip>
                      {/*
                      The failure detail is otherwise only in the hover
                      tooltip, so assistive tech never reaches it (WCAG 1.3.1).
                    */}
                      {server.error && (
                        <span className="sr-only">
                          {t("mcp.servers.statusErrorDetail", {
                            name: server.name,
                            error: server.error,
                          })}
                        </span>
                      )}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="iconSm"
                          aria-label={t("mcp.servers.actionsMenu", {
                            defaultValue: "Actions for {{name}}",
                            name: server.name,
                          })}
                          data-testid={`mcp-server-menu-button-${server.name}`}
                          className="text-muted-foreground hover:bg-accent"
                        >
                          <ForwardedIconComponent
                            name="Ellipsis"
                            className="h-5 w-5"
                          />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => handleEdit(server.name)}
                        >
                          <ForwardedIconComponent
                            name="SquarePen"
                            className="mr-2 h-4 w-4"
                          />
                          {t("mcp.servers.editMenuItem")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openDeleteModal(server)}
                          className="text-destructive"
                        >
                          <ForwardedIconComponent
                            name="Trash2"
                            className="mr-2 h-4 w-4"
                          />
                          {t("mcp.servers.deleteMenuItem")}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                ))}
              </ul>
            )}
            {editOpen && (
              <AddMcpServerModal
                open={editOpen}
                setOpen={setEditOpen}
                initialData={editInitialData}
              />
            )}
            <DeleteConfirmationModal
              open={deleteModalOpen}
              setOpen={setDeleteModalOpen}
              onConfirm={() => {
                if (serverToDelete) handleDelete(serverToDelete);
                setDeleteModalOpen(false);
                setServerToDelete(null);
              }}
              description={"MCP Server"}
            />
          </>
        ) : (
          // The spinner is aria-hidden, so without a status region the load
          // is silent to assistive tech (WCAG 4.1.3).
          <div
            role="status"
            data-testid="mcp-servers-loading"
            className="flex h-full w-full items-center justify-center"
          >
            <Loading />
            <span className="sr-only">{t("mcp.servers.loadingServers")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
