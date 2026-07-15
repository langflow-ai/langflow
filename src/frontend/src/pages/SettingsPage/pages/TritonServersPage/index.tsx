import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
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
import { useDeleteTritonServer } from "@/controllers/API/queries/triton/use-delete-triton-server";
import { useGetTritonServers } from "@/controllers/API/queries/triton/use-get-triton-servers";
import AddTritonModelsToVariablesModal from "@/modals/addTritonModelsToVariablesModal";
import AddTritonServerModal from "@/modals/addTritonServerModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import type { TritonServerType } from "@/types/triton";

export default function TritonServersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: servers, isError, error, refetch } = useGetTritonServers();
  const { mutate: deleteServer } = useDeleteTritonServer();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editInitialData, setEditInitialData] =
    useState<TritonServerType | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [serverToDelete, setServerToDelete] = useState<TritonServerType | null>(
    null,
  );
  const [modelsToVarsOpen, setModelsToVarsOpen] = useState(false);
  const [serverForVars, setServerForVars] = useState<TritonServerType | null>(
    null,
  );

  const handleEdit = (server: TritonServerType) => {
    setEditInitialData(server);
    setEditOpen(true);
  };

  const handleDelete = (server: TritonServerType) => {
    deleteServer(
      { server_id: server.id },
      {
        onError: (e: Error) =>
          setErrorData({
            title: t("triton.servers.errorDeleting"),
            list: [e.message],
          }),
        onSuccess: () =>
          setSuccessData({ title: t("triton.servers.deletedSuccess") }),
      },
    );
  };

  const openDeleteModal = (server: TritonServerType) => {
    setServerToDelete(server);
    setDeleteModalOpen(true);
  };

  const openModelsToVars = (server: TritonServerType) => {
    setServerForVars(server);
    setModelsToVarsOpen(true);
  };

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("triton.servers.title")}
            <ForwardedIconComponent
              name="Nvidia"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("triton.servers.description")}
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <Button
            variant="primary"
            onClick={() => setAddOpen(true)}
            data-testid="add-triton-server-button-page"
          >
            <ForwardedIconComponent name="Plus" className="w-4" />
            <span>{t("triton.servers.addButton")}</span>
          </Button>
          <AddTritonServerModal open={addOpen} setOpen={setAddOpen} />
        </div>
      </div>
      <div className="flex h-full flex-col gap-2">
        {servers ? (
          <>
            {servers.length === 0 ? (
              <div className="w-full pt-8 text-center text-sm text-muted-foreground">
                {t("triton.servers.noServersAdded")}
              </div>
            ) : (
              <div className="text-sm font-medium text-muted-foreground">
                {t("triton.servers.addedServers")}
              </div>
            )}
            <div className="flex flex-col gap-1">
              {servers.map((server, index) => (
                <div
                  key={server.id}
                  className="flex items-center justify-between rounded-lg px-3 py-2 shadow-sm transition-colors hover:bg-accent"
                >
                  <div className="flex flex-col gap-0.5">
                    <button
                      type="button"
                      onClick={() =>
                        navigate(`/settings/triton-servers/${server.id}`)
                      }
                      className="text-left text-sm font-medium hover:underline"
                      data-testid={`triton-server-name-${index}`}
                    >
                      {server.name}
                    </button>
                    <span className="font-mono text-xs text-muted-foreground">
                      {server.base_url}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <ShadTooltip
                      content={
                        server.has_auth_token
                          ? t("triton.servers.hasToken")
                          : t("triton.servers.noToken")
                      }
                    >
                      <span className="cursor-default text-xs text-muted-foreground">
                        <ForwardedIconComponent
                          name={server.has_auth_token ? "KeyRound" : "Globe"}
                          className="h-4 w-4"
                        />
                      </span>
                    </ShadTooltip>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="iconSm"
                          data-testid={`triton-server-menu-button-${server.id}`}
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
                          onClick={() =>
                            navigate(`/settings/triton-servers/${server.id}`)
                          }
                        >
                          <ForwardedIconComponent
                            name="ExternalLink"
                            className="mr-2 h-4 w-4"
                          />
                          {t("triton.servers.openDetailItem")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEdit(server)}>
                          <ForwardedIconComponent
                            name="SquarePen"
                            className="mr-2 h-4 w-4"
                          />
                          {t("triton.servers.editMenuItem")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openModelsToVars(server)}
                        >
                          <ForwardedIconComponent
                            name="Boxes"
                            className="mr-2 h-4 w-4"
                          />
                          {t("triton.servers.addToVariablesItem")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openDeleteModal(server)}
                          className="text-destructive"
                        >
                          <ForwardedIconComponent
                            name="Trash2"
                            className="mr-2 h-4 w-4"
                          />
                          {t("triton.servers.deleteMenuItem")}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              ))}
            </div>
            {editOpen && editInitialData && (
              <AddTritonServerModal
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
              description={"Triton Server"}
            />
            {modelsToVarsOpen && serverForVars && (
              <AddTritonModelsToVariablesModal
                open={modelsToVarsOpen}
                setOpen={setModelsToVarsOpen}
                server={serverForVars}
              />
            )}
          </>
        ) : isError ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-4 py-8">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <ForwardedIconComponent
                name="TriangleAlert"
                className="h-5 w-5"
              />
              <span data-testid="triton-servers-error">
                {error?.message || t("triton.servers.errorFetching")}
              </span>
            </div>
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => refetch()}
                data-testid="triton-servers-retry"
              >
                <ForwardedIconComponent name="RefreshCw" className="h-4 w-4" />
                {t("triton.detail.retry")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigate("/login");
                }}
              >
                {t("auth.adminLoginButton")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        )}
      </div>
    </div>
  );
}
