import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
  PermissionsProvider,
  usePermissions,
} from "@/contexts/permissionsContext";
import { useUpdateUser } from "@/controllers/API/queries/auth";
import {
  usePatchFolders,
  usePostFolders,
  usePostUploadFolders,
} from "@/controllers/API/queries/folders";
import { useGetDownloadFolders } from "@/controllers/API/queries/folders/use-get-download-folders";
import {
  ENABLE_CUSTOM_PARAM,
  ENABLE_FILE_MANAGEMENT,
  ENABLE_KNOWLEDGE_BASES,
  ENABLE_MCP_NOTICE,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import { customGetDownloadFolderBlob } from "@/customization/utils/custom-get-download-folders";
import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import useAuthStore from "@/stores/authStore";
import type { FlowType } from "@/types/flow";
import { extractApiErrorMessages } from "@/utils/apiError";
import { getProjectDisplayName } from "@/utils/project-display-name";
import type { FolderType } from "../../../../../pages/MainPage/entities";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../../stores/foldersStore";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import { cn } from "../../../../../utils/utils";
import useFileDrop from "../../hooks/use-on-file-drop";
import { SidebarFolderSkeleton } from "../sidebarFolderSkeleton";
import { HeaderButtons } from "./components/header-buttons";
import { InputEditFolderName } from "./components/input-edit-folder-name";
import { MCPServerNotice } from "./components/mcp-server-notice";
import { SelectOptions } from "./components/select-options";

type SideBarFoldersButtonsComponentProps = {
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  handleFilesClick?: () => void;
};

type UploadedFlowFile = FlowType | { flows: FlowType[] };

const ProjectRenamePermission = ({
  projectId,
  children,
}: {
  projectId: string;
  children: (canRename: boolean) => ReactNode;
}) => {
  const { can } = usePermissions();
  return children(can(projectId, "write"));
};

const SideBarFoldersButtonsComponent = ({
  handleChangeFolder,
  handleDeleteFolder,
  handleFilesClick,
}: SideBarFoldersButtonsComponentProps) => {
  const location = useLocation();
  const pathname = location.pathname;
  const folders = useFolderStore((state) => state.folders);
  const loading = !folders;
  const refInput = useRef<HTMLInputElement>(null);

  const _navigate = useCustomNavigate();

  const currentFolder = pathname.split("/");
  const urlWithoutPath =
    pathname.split("/").length < (ENABLE_CUSTOM_PARAM ? 5 : 4);
  const checkPathFiles = pathname.includes("assets");

  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId && !checkPathFiles) {
      return true;
    }
    return currentFolder.includes(itemId);
  };

  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const isMobile = useIsMobile({ maxWidth: 1024 });
  const folderIdDragging = useFolderStore((state) => state.folderIdDragging);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const folderId = useParams().folderId ?? myCollectionId ?? "";

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(folderId);
  const uploadFlow = useUploadFlow();
  const [foldersNames, setFoldersNames] = useState<Record<string, string>>({});
  const [editFolders, setEditFolderName] = useState(
    folders.map((obj) => ({ id: obj.id!, edit: false })) ?? [],
  );

  // Committing or cancelling a rename unmounts the input while it still holds
  // focus, dropping focus to <body> and forcing a keyboard user to tab from the
  // top of the page. Hand focus back to the project's nav item instead — but
  // only when focus was actually lost, so clicking straight to another control
  // isn't yanked back here.
  const renamingFolderId =
    editFolders.find((folder) => folder.edit)?.id ?? null;
  const previousRenamingFolderId = useRef<string | null>(null);

  useEffect(() => {
    const justFinished = previousRenamingFolderId.current;
    previousRenamingFolderId.current = renamingFolderId;

    if (!justFinished || renamingFolderId) return;
    if (document.activeElement && document.activeElement !== document.body) {
      return;
    }

    document.getElementById(`sidebar-nav-${justFinished}`)?.focus();
  }, [renamingFolderId]);

  const isFetchingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  const { mutate: mutateDownloadFolder } = useGetDownloadFolders({});
  const { mutate: mutateAddFolder, isPending } = usePostFolders();
  const { mutate: mutateUpdateFolder } = usePatchFolders();
  const { mutate } = usePostUploadFolders();

  const checkHoveringFolder = (folderId: string) => {
    if (folderId === folderIdDragging) {
      return "bg-accent text-accent-foreground";
    }
  };

  const isFetchingFolder = !!useIsFetching({
    queryKey: ["useGetFolder"],
    exact: false,
  });

  const isDeletingFolder = !!useIsMutating({
    mutationKey: ["useDeleteFolders"],
  });

  const isUpdatingFolder =
    isFetchingFolders ||
    isFetchingFolder ||
    isPending ||
    loading ||
    isDeletingFolder;

  const handleUploadFlowsToFolder = () => {
    createFileUpload().then((files: File[]) => {
      if (files?.length === 0) {
        return;
      }

      getObjectsFromFilelist<UploadedFlowFile>(files)
        .then((objects) => {
          if (objects.every((flow) => flow.data?.nodes)) {
            uploadFlow({ files })
              .then(() => {
                setSuccessData({
                  title: t("sidebar.uploadSuccess"),
                });
              })
              .catch((error) => {
                setErrorData({
                  title: t("errors.upload"),
                  list: [
                    error instanceof Error ? error.message : String(error),
                  ],
                });
              });
          } else {
            files.forEach((folder) => {
              const formData = new FormData();
              formData.append("file", folder);
              mutate(
                { formData },
                {
                  onSuccess: () => {
                    setSuccessData({
                      title: t("sidebar.projectUploadSuccess"),
                    });
                  },
                  onError: (err) => {
                    console.error(err);
                    setErrorData({
                      title: t("sidebar.projectUploadError"),
                      list: [
                        err?.response?.data?.detail ??
                          (err instanceof Error ? err.message : String(err)),
                      ],
                    });
                  },
                },
              );
            });
          }
        })
        .catch((error) => {
          setErrorData({
            title: t("errors.upload"),
            list: [error instanceof Error ? error.message : String(error)],
          });
        });
    });
  };

  const handleDownloadFolder = (id: string, folderName: string) => {
    mutateDownloadFolder(
      {
        folderId: id,
      },
      {
        onSuccess: (response) => {
          customGetDownloadFolderBlob(response, id, folderName, setSuccessData);
        },
        onError: (e) => {
          setErrorData({
            title: t("sidebar.downloadError"),
          });
        },
      },
    );
  };

  function addNewFolder() {
    mutateAddFolder(
      {
        data: {
          name: "New Project",
          parent_id: null,
          description: "",
        },
      },
      {
        onSuccess: (folder) => {
          track("Create New Project");
          handleChangeFolder!(folder.id);
        },
        onError: (error) => {
          setErrorData({
            title: t("sidebar.projectCreateError"),
            list: extractApiErrorMessages(error),
          });
        },
      },
    );
  }

  function handleEditFolderName(e, folderId): void {
    const {
      target: { value },
    } = e;
    setFoldersNames((old) => ({
      ...old,
      [folderId]: value,
    }));
  }

  useEffect(() => {
    if (folders && folders.length > 0) {
      setEditFolderName(folders.map((obj) => ({ id: obj.id!, edit: false })));
    }
  }, [folders]);

  const handleEditNameFolder = async (item) => {
    const newEditFolders = editFolders.map((obj) => {
      if (obj.id === item.id) {
        return { id: item.id, edit: false };
      }
      return { id: obj.id, edit: false };
    });
    setEditFolderName(newEditFolders);
    if (foldersNames[item.id].trim() !== "") {
      setFoldersNames((old) => ({
        ...old,
        [item.id]: foldersNames[item.id],
      }));
      const body = {
        ...item,
        name: foldersNames[item.id],
        flows: item.flows?.length > 0 ? item.flows : [],
        components: item.components?.length > 0 ? item.components : [],
      };

      mutateUpdateFolder(
        {
          data: body,
          folderId: item.id!,
        },
        {
          onSuccess: (updatedFolder) => {
            const updatedFolderIndex = folders.findIndex(
              (f) => f.id === updatedFolder.id,
            );

            const updateFolders = [...folders];
            updateFolders[updatedFolderIndex] = updatedFolder;

            setFoldersNames({});
            setEditFolderName(
              folders.map((obj) => ({
                id: obj.id!,
                edit: false,
              })),
            );
          },
        },
      );
    } else {
      setFoldersNames((old) => ({
        ...old,
        [item.id]: item.name,
      }));
    }
  };

  const handleDoubleClick = (event, item) => {
    event.stopPropagation();
    event.preventDefault();

    handleSelectFolderToRename(item);
  };

  const handleSelectFolderToRename = (item) => {
    if (!foldersNames[item.id]) {
      setFoldersNames({ [item.id]: item.name });
    }

    if (editFolders.some((obj) => obj.id === item.id)) {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.id === item.id) {
          return { id: item.id, edit: true };
        }
        return { id: obj.id, edit: false };
      });
      setEditFolderName(newEditFolders);
      takeSnapshot();
      return;
    }

    setEditFolderName((old) => [...old, { id: item.id, edit: true }]);
    setFoldersNames((oldFolder) => ({
      ...oldFolder,
      [item.id]: item.name,
    }));
    takeSnapshot();
  };

  const handleKeyDownFn = (e, item) => {
    if (e.key === "Escape") {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.id === item.id) {
          return { id: item.id, edit: false };
        }
        return { id: obj.id, edit: false };
      });
      setEditFolderName(newEditFolders);
      setFoldersNames({});
      setEditFolderName(
        folders.map((obj) => ({
          id: obj.id!,
          edit: false,
        })),
      );
    }
    if (e.key === "Enter") {
      refInput.current?.blur();
    }
  };

  const [hoveredFolderId, setHoveredFolderId] = useState<string | null>(null);

  const userData = useAuthStore((state) => state.userData);
  const { mutate: updateUser } = useUpdateUser();
  const userDismissedMcpDialog = userData?.optins?.mcp_dialog_dismissed;

  const [isDismissedMcpDialog, setIsDismissedMcpDialog] = useState(
    userDismissedMcpDialog,
  );

  const handleDismissMcpDialog = () => {
    setIsDismissedMcpDialog(true);
    updateUser({
      user_id: userData?.id!,
      user: {
        optins: {
          ...userData?.optins,
          mcp_dialog_dismissed: true,
        },
      },
    });
  };

  const handleFilesNavigation = () => {
    _navigate("/assets/files");
  };

  const handleKnowledgeNavigation = () => {
    _navigate("/assets/knowledge-bases");
  };

  return (
    <Sidebar
      collapsible={isMobile ? "offcanvas" : "none"}
      data-testid="project-sidebar"
      aria-labelledby="project-sidebar-title"
    >
      <SidebarHeader className="px-4 py-1">
        <HeaderButtons
          handleUploadFlowsToFolder={handleUploadFlowsToFolder}
          isUpdatingFolder={isUpdatingFolder}
          isPending={isPending}
          addNewFolder={addNewFolder}
        />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="p-4 py-2">
          <SidebarGroupContent>
            <PermissionsProvider
              resourceType="project"
              resourceIds={folders
                .map((folder) => folder.id ?? "")
                .filter(Boolean)}
            >
              <SidebarMenu>
                {!loading ? (
                  folders.length === 0 ? (
                    <div className="px-2 py-5 text-center text-sm text-muted-foreground">
                      {t("sidebar.emptyMessage")}
                    </div>
                  ) : (
                    folders.map((item) => {
                      const editFolderName = editFolders?.filter(
                        (folder) => folder.id === item.id,
                      )[0];
                      return (
                        <SidebarMenuItem
                          key={item.id}
                          className="group/menu-button"
                          data-project-id={item.id}
                          onMouseEnter={() => setHoveredFolderId(item.id!)}
                          onMouseLeave={() => setHoveredFolderId(null)}
                        >
                          <div className="relative flex w-full">
                            <ProjectRenamePermission projectId={item.id!}>
                              {(canRename) => (
                                <SidebarMenuButton
                                  size="md"
                                  onDragOver={(e) => dragOver(e, item.id!)}
                                  onDragEnter={(e) => dragEnter(e, item.id!)}
                                  onDragLeave={dragLeave}
                                  onDrop={(e) => onDrop(e, item.id!)}
                                  key={item.id}
                                  data-testid={`sidebar-nav-${item.id}`}
                                  id={`sidebar-nav-${item.id}`}
                                  isActive={checkPathName(item.id!)}
                                  onClick={() => handleChangeFolder!(item.id!)}
                                  onDoubleClick={(event) => {
                                    if (canRename) {
                                      handleDoubleClick(event, item);
                                    }
                                  }}
                                  className={cn(
                                    "flex-grow pr-8",
                                    hoveredFolderId === item.id && "bg-accent",
                                    checkHoveringFolder(item.id!),
                                  )}
                                >
                                  <div className="flex w-full items-center justify-between gap-2">
                                    <div className="flex flex-1 items-center gap-2">
                                      {editFolderName?.edit &&
                                      !isUpdatingFolder ? (
                                        <InputEditFolderName
                                          handleEditFolderName={
                                            handleEditFolderName
                                          }
                                          item={item}
                                          refInput={refInput}
                                          handleKeyDownFn={handleKeyDownFn}
                                          handleEditNameFolder={
                                            handleEditNameFolder
                                          }
                                          editFolderName={editFolderName}
                                          foldersNames={foldersNames}
                                          handleKeyDown={handleKeyDown}
                                        />
                                      ) : (
                                        <span
                                          className="block w-0 grow truncate text-sm opacity-100"
                                          // The sidebar cannot be widened, so a
                                          // truncated name is otherwise
                                          // unreadable. With one default project
                                          // per user the list fills with rows
                                          // that differ only in the truncated
                                          // part.
                                          title={getProjectDisplayName(item, t)}
                                        >
                                          {getProjectDisplayName(item, t)}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </SidebarMenuButton>
                              )}
                            </ProjectRenamePermission>
                            <div className="absolute right-2 top-[0.45rem] flex items-center hover:text-foreground">
                              <SelectOptions
                                item={item}
                                handleDeleteFolder={handleDeleteFolder}
                                handleDownloadFolder={() =>
                                  handleDownloadFolder(item.id!, item.name)
                                }
                                handleSelectFolderToRename={
                                  handleSelectFolderToRename
                                }
                                checkPathName={checkPathName}
                              />
                            </div>
                          </div>
                        </SidebarMenuItem>
                      );
                    })
                  )
                ) : (
                  <>
                    <SidebarFolderSkeleton />
                    <SidebarFolderSkeleton />
                  </>
                )}
              </SidebarMenu>
            </PermissionsProvider>
          </SidebarGroupContent>
        </SidebarGroup>
        <div className="flex-1" />

        {ENABLE_MCP_NOTICE && !isDismissedMcpDialog && (
          <div className="p-2">
            <MCPServerNotice handleDismissDialog={handleDismissMcpDialog} />
          </div>
        )}
      </SidebarContent>
      {ENABLE_FILE_MANAGEMENT && (
        <SidebarFooter className="border-t">
          <div className="grid w-full items-center gap-2 p-2">
            {ENABLE_KNOWLEDGE_BASES && (
              <SidebarMenuButton
                onClick={handleKnowledgeNavigation}
                size="md"
                className="text-sm"
              >
                <ForwardedIconComponent name="Library" className="h-4 w-4" />
                {t("sidebar.knowledge")}
              </SidebarMenuButton>
            )}
            <SidebarMenuButton
              onClick={handleFilesNavigation}
              size="md"
              className="text-sm"
            >
              <ForwardedIconComponent name="File" className="h-4 w-4" />
              {t("sidebar.myFiles")}
            </SidebarMenuButton>
          </div>
        </SidebarFooter>
      )}
    </Sidebar>
  );
};
export default SideBarFoldersButtonsComponent;
