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
  DEFAULT_FOLDER,
  DEFAULT_FOLDER_DEPRECATED,
} from "@/constants/constants";
import { useUpdateUser } from "@/controllers/API/queries/auth";
import {
  usePatchFolders,
  usePostFolders,
  usePostUploadFolders,
} from "@/controllers/API/queries/folders";
import { useGetDownloadFolders } from "@/controllers/API/queries/folders/use-get-download-folders";
import {
  ENABLE_CUSTOM_PARAM,
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_FILE_MANAGEMENT,
  ENABLE_MCP_NOTICE,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import useAuthStore from "@/stores/authStore";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { FolderType } from "../../../../../pages/MainPage/entities";
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

  const navigate = useCustomNavigate();

  const currentFolder = pathname.split("/");
  const urlWithoutPath =
    pathname.split("/").length < (ENABLE_CUSTOM_PARAM ? 5 : 4);
  const checkPathFiles = pathname.includes("files");

  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId && !checkPathFiles) {
      return true;
    }
    return currentFolder.includes(itemId);
  };

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const isMobile = useIsMobile({ maxWidth: 1024 });
  const folderIdDragging = useFolderStore((state) => state.folderIdDragging);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const folderId = useParams().folderId ?? myCollectionId ?? "";

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(folderId);
  const uploadFlow = useUploadFlow();
  const [foldersNames, setFoldersNames] = useState({});
  const [editFolders, setEditFolderName] = useState(
    folders.map((obj) => ({ name: obj.name, edit: false })) ?? [],
  );

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

      getObjectsFromFilelist<any>(files).then((objects) => {
        if (objects.every((flow) => flow.data?.nodes)) {
          uploadFlow({ files }).then(() => {
            setSuccessData({
              title: "Uploaded successfully",
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
                    title: "Project uploaded successfully.",
                  });
                },
                onError: (err) => {
                  console.log(err);
                  setErrorData({
                    title: `Error on uploading your project, try dragging it into an existing project.`,
                    list: [err["response"]["data"]["message"]],
                  });
                },
              },
            );
          });
        }
      });
    });
  };

  const handleDownloadFolder = (id: string) => {
    mutateDownloadFolder(
      {
        folderId: id,
      },
      {
        onSuccess: (response) => {
          // Create a blob from the response data
          const blob = new Blob([response.data], {
            type: "application/x-zip-compressed",
          });

          const url = window.URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;

          // Get filename from header or use default
          const filename =
            response.headers?.["content-disposition"]
              ?.split("filename=")[1]
              ?.replace(/['"]/g, "") ?? "flows.zip";

          link.setAttribute("download", filename);
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);

          track("Project Exported", { folderId: id });
        },
        onError: (e) => {
          setErrorData({
            title: `An error occurred while downloading your project.`,
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
      },
    );
  }

  function handleEditFolderName(e, name): void {
    const {
      target: { value },
    } = e;
    setFoldersNames((old) => ({
      ...old,
      [name]: value,
    }));
  }

  useEffect(() => {
    if (folders && folders.length > 0) {
      setEditFolderName(
        folders.map((obj) => ({ name: obj.name, edit: false })),
      );
    }
  }, [folders]);

  const handleEditNameFolder = async (item) => {
    const newEditFolders = editFolders.map((obj) => {
      if (obj.name === item.name) {
        return { name: item.name, edit: false };
      }
      return { name: obj.name, edit: false };
    });
    setEditFolderName(newEditFolders);
    if (foldersNames[item.name].trim() !== "") {
      setFoldersNames((old) => ({
        ...old,
        [item.name]: foldersNames[item.name],
      }));
      const body = {
        ...item,
        name: foldersNames[item.name],
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
                name: obj.name,
                edit: false,
              })),
            );
          },
        },
      );
    } else {
      setFoldersNames((old) => ({
        ...old,
        [item.name]: item.name,
      }));
    }
  };

  const handleDoubleClick = (event, item) => {
    if (item.name === DEFAULT_FOLDER_DEPRECATED) {
      return;
    }

    event.stopPropagation();
    event.preventDefault();

    handleSelectFolderToRename(item);
  };

  const handleSelectFolderToRename = (item) => {
    if (!foldersNames[item.name]) {
      setFoldersNames({ [item.name]: item.name });
    }

    if (editFolders.find((obj) => obj.name === item.name)?.name) {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.name === item.name) {
          return { name: item.name, edit: true };
        }
        return { name: obj.name, edit: false };
      });
      setEditFolderName(newEditFolders);
      takeSnapshot();
      return;
    }

    setEditFolderName((old) => [...old, { name: item.name, edit: true }]);
    setFoldersNames((oldFolder) => ({
      ...oldFolder,
      [item.name]: item.name,
    }));
    takeSnapshot();
  };

  const handleKeyDownFn = (e, item) => {
    if (e.key === "Escape") {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.name === item.name) {
          return { name: item.name, edit: false };
        }
        return { name: obj.name, edit: false };
      });
      setEditFolderName(newEditFolders);
      setFoldersNames({});
      setEditFolderName(
        folders.map((obj) => ({
          name: obj.name,
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

  return (
    <Sidebar
      collapsible={isMobile ? "offcanvas" : "none"}
      data-testid="project-sidebar"
      className="bg-gradient-to-b from-background via-background/90 to-background/80 dark:from-background dark:via-background/80 dark:to-background/60 backdrop-blur-xl border-r border-border/50 shadow-xl shadow-background/10 rounded-xl m-2 transition-all duration-300"
    >
      <SidebarHeader className="px-4 py-4 border-b border-border/50 bg-background/60 dark:bg-background/40 rounded-t-xl">
        <div className="space-y-3">
          <HeaderButtons
            handleUploadFlowsToFolder={handleUploadFlowsToFolder}
            isUpdatingFolder={isUpdatingFolder}
            isPending={isPending}
            addNewFolder={addNewFolder}
          />
          {!ENABLE_DATASTAX_LANGFLOW && (
            <div className="flex w-full items-center" data-testid="button-store">
              <SidebarMenuButton
                size="md"
                className="text-sm font-medium bg-primary/10 hover:bg-primary/20 text-primary hover:text-primary transition-all duration-300 rounded-lg w-full justify-start gap-2 shadow-sm hover:shadow-md hover:scale-[1.02] dark:bg-primary/20 dark:hover:bg-primary/30 dark:text-primary"
                onClick={() => {
                  window.open("/store", "_blank");
                }}
              >
                <ForwardedIconComponent name="Store" className="h-4 w-4" />
                Store
              </SidebarMenuButton>
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent className="scrollbar-thin scrollbar-thumb-border scrollbar-track-background/50">
        <SidebarGroup className="p-4 py-3">
          <div className="mb-4 px-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold bg-gradient-to-r from-primary/90 to-primary bg-clip-text text-transparent dark:from-primary/80 dark:to-primary">Projects</h2>
            <div className="h-[2px] flex-1 mx-3 bg-gradient-to-r from-border/50 to-transparent"></div>
          </div>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {!loading ? (
                folders.map((item, index) => {
                  const editFolderName = editFolders?.filter(
                    (folder) => folder.name === item.name,
                  )[0];
                  return (
                    <SidebarMenuItem
                      key={index}
                      className="group/menu-button transition-all duration-200"
                      onMouseEnter={() => setHoveredFolderId(item.id!)}
                      onMouseLeave={() => setHoveredFolderId(null)}
                    >
                      <div className="relative flex w-full rounded-lg overflow-hidden">
                        <SidebarMenuButton
                          size="md"
                          onDragOver={(e) => dragOver(e, item.id!)}
                          onDragEnter={(e) => dragEnter(e, item.id!)}
                          onDragLeave={dragLeave}
                          onDrop={(e) => onDrop(e, item.id!)}
                          key={item.id}
                          data-testid={`sidebar-nav-${item.name}`}
                          id={`sidebar-nav-${item.name}`}
                          isActive={checkPathName(item.id!)}
                          onClick={() => handleChangeFolder!(item.id!)}
                          className={cn(
                            "flex-grow pr-8 transition-all duration-300",
                            "hover:bg-primary/10 hover:shadow-md hover:translate-x-1 dark:hover:bg-primary/20",
                            hoveredFolderId === item.id && "bg-primary/10 shadow-sm dark:bg-primary/20",
                            checkPathName(item.id!) && "bg-primary/20 shadow-md translate-x-1 font-medium dark:bg-primary/30",
                            checkHoveringFolder(item.id!),
                            "before:absolute before:left-0 before:top-0 before:h-full before:w-[2px] before:bg-primary/0 before:transition-all",
                            checkPathName(item.id!) && "before:bg-primary"
                          )}
                        >
                          <div
                            onDoubleClick={(event) => {
                              handleDoubleClick(event, item);
                            }}
                            className="flex w-full items-center justify-between gap-2 py-2.5"
                          >
                            <div className="flex flex-1 items-center gap-3">
                              <div className={cn(
                                "p-1 rounded-md transition-colors duration-300",
                                checkPathName(item.id!) ? "bg-primary/10 dark:bg-primary/20" : "bg-transparent",
                              )}>
                                <ForwardedIconComponent 
                                  name="Folder" 
                                  className={cn(
                                    "h-4 w-4 transition-colors duration-300",
                                    checkPathName(item.id!) ? "text-primary" : "text-muted-foreground dark:text-muted-foreground"
                                  )} 
                                />
                              </div>
                              {editFolderName?.edit && !isUpdatingFolder ? (
                                <InputEditFolderName
                                  handleEditFolderName={handleEditFolderName}
                                  item={item}
                                  refInput={refInput}
                                  handleKeyDownFn={handleKeyDownFn}
                                  handleEditNameFolder={handleEditNameFolder}
                                  editFolderName={editFolderName}
                                  foldersNames={foldersNames}
                                  handleKeyDown={handleKeyDown}
                                />
                              ) : (
                                <span className="block w-0 grow truncate text-sm opacity-100 transition-colors duration-300 dark:text-foreground">
                                  {item.name === DEFAULT_FOLDER_DEPRECATED
                                    ? DEFAULT_FOLDER
                                    : item.name}
                                </span>
                              )}
                            </div>
                          </div>
                        </SidebarMenuButton>
                        <div
                          className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover/menu-button:opacity-100 transition-all duration-300 scale-90 group-hover/menu-button:scale-100"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <SelectOptions
                            item={item}
                            index={index}
                            handleDeleteFolder={handleDeleteFolder}
                            handleDownloadFolder={handleDownloadFolder}
                            handleSelectFolderToRename={handleSelectFolderToRename}
                            checkPathName={checkPathName}
                          />
                        </div>
                      </div>
                    </SidebarMenuItem>
                  );
                })
              ) : (
                <div className="space-y-2 animate-pulse">
                  <SidebarFolderSkeleton />
                  <SidebarFolderSkeleton />
                </div>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <div className="flex-1" />

        {ENABLE_MCP_NOTICE && !isDismissedMcpDialog && (
          <div className="p-3">
            <MCPServerNotice handleDismissDialog={handleDismissMcpDialog} />
          </div>
        )}
      </SidebarContent>
      {ENABLE_FILE_MANAGEMENT && (
        <SidebarFooter className="border-t border-border/50 bg-background/60 dark:bg-background/40 rounded-b-xl">
          <div className="px-4 py-3">
            <div className="mb-3 px-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold bg-gradient-to-r from-primary/90 to-primary bg-clip-text text-transparent dark:from-primary/80 dark:to-primary">Resources</h2>
              <div className="h-[2px] flex-1 mx-3 bg-gradient-to-r from-border/50 to-transparent"></div>
            </div>
            <SidebarMenuButton
              isActive={checkPathFiles}
              onClick={() => handleFilesClick?.()}
              size="md"
              className={cn(
                "text-sm font-medium transition-all duration-300 rounded-lg w-full justify-start gap-3",
                "hover:bg-primary/10 hover:shadow-md hover:translate-x-1 dark:hover:bg-primary/20",
                checkPathFiles && "bg-primary/20 shadow-md translate-x-1 dark:bg-primary/30"
              )}
            >
              <div className={cn(
                "p-1 rounded-md transition-colors duration-300",
                checkPathFiles ? "bg-primary/10 dark:bg-primary/20" : "bg-transparent"
              )}>
                <ForwardedIconComponent 
                  name="File" 
                  className={cn(
                    "h-4 w-4 transition-colors duration-300",
                    checkPathFiles ? "text-primary" : "text-muted-foreground dark:text-muted-foreground"
                  )} 
                />
              </div>
              My Files
            </SidebarMenuButton>
          </div>
        </SidebarFooter>
      )}
    </Sidebar>
  );
};
export default SideBarFoldersButtonsComponent;
