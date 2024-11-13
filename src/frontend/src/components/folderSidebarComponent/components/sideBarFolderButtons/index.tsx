import ShadTooltip from "@/components/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import {
  usePatchFolders,
  usePostFolders,
  usePostUploadFolders,
} from "@/controllers/API/queries/folders";
import { useGetDownloadFolders } from "@/controllers/API/queries/folders/use-get-download-folders";
import { ENABLE_CUSTOM_PARAM } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { FolderType } from "../../../../pages/MainPage/entities";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { handleKeyDown } from "../../../../utils/reactflowUtils";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { Input } from "../../../ui/input";
import useFileDrop from "../../hooks/use-on-file-drop";
import { SidebarFolderSkeleton } from "../sidebarFolderSkeleton";

type SideBarFoldersButtonsComponentProps = {
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
};
const SideBarFoldersButtonsComponent = ({
  handleChangeFolder,
  handleDeleteFolder,
}: SideBarFoldersButtonsComponentProps) => {
  const location = useLocation();
  const pathname = location.pathname;
  const folders = useFolderStore((state) => state.folders);

  const isFetchingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });
  const loading = !folders;
  const refInput = useRef<HTMLInputElement>(null);
  const [foldersNames, setFoldersNames] = useState({});
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [editFolders, setEditFolderName] = useState(
    folders.map((obj) => ({ name: obj.name, edit: false })) ?? [],
  );
  const currentFolder = pathname.split("/");
  const urlWithoutPath =
    pathname.split("/").length < (ENABLE_CUSTOM_PARAM ? 5 : 4);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId) {
      return true;
    }
    return currentFolder.includes(itemId);
  };
  const folderId = useParams().folderId ?? myCollectionId ?? "";
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const uploadFlow = useUploadFlow();

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(folderId);

  const { mutate } = usePostUploadFolders();

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
                    title: "Folder uploaded successfully.",
                  });
                },
                onError: (err) => {
                  console.log(err);
                  setErrorData({
                    title: `Error on uploading your folder, try dragging it into an existing folder.`,
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

  const { mutate: mutateDownloadFolder } = useGetDownloadFolders();

  const handleDownloadFolder = (id: string) => {
    mutateDownloadFolder(
      {
        folderId: id,
      },
      {
        onSuccess: (data) => {
          data.folder_name = data?.name || "folder";
          data.folder_description = data?.description || "";

          const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
            JSON.stringify(data),
          )}`;

          const link = document.createElement("a");
          link.href = jsonString;
          link.download = `${data?.name}.json`;

          link.click();
          track("Folder Exported", { folderId: id! });
        },
        onError: () => {
          setErrorData({
            title: `An error occurred while downloading folder.`,
          });
        },
      },
    );
  };

  const { mutate: mutateAddFolder, isPending } = usePostFolders();
  const { mutate: mutateUpdateFolder } = usePatchFolders();

  function addNewFolder() {
    mutateAddFolder(
      {
        data: {
          name: "New Folder",
          parent_id: null,
          description: "",
        },
      },
      {
        onSuccess: (folder) => {
          track("Create New Folder");
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

  const HeaderButtons = () => (
    <div className="flex shrink-0 items-center justify-between gap-2">
      <SidebarTrigger className="lg:hidden">
        <IconComponent name="PanelLeftClose" className="h-4 w-4" />
      </SidebarTrigger>

      <div className="flex-1 text-sm font-semibold">Folders</div>
      <div className="flex items-center gap-1">
        <UploadFolderButton
          onClick={handleUploadFlowsToFolder}
          disabled={isUpdatingFolder}
        />
        <AddFolderButton
          onClick={addNewFolder}
          disabled={isUpdatingFolder}
          loading={isPending}
        />
      </div>
    </div>
  );

  const AddFolderButton = ({ onClick, disabled, loading }) => (
    <ShadTooltip content="Create new folder" styleClasses="z-50">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 border-0 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
        onClick={onClick}
        data-testid="add-folder-button"
        disabled={disabled}
        loading={loading}
      >
        <IconComponent name="Plus" className="h-4 w-4" />
      </Button>
    </ShadTooltip>
  );

  const UploadFolderButton = ({ onClick, disabled }) => (
    <ShadTooltip content="Upload a flow" styleClasses="z-50">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 border-0 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
        onClick={onClick}
        data-testid="upload-folder-button"
        disabled={disabled}
      >
        <IconComponent name="Upload" className="h-4 w-4" />
      </Button>
    </ShadTooltip>
  );

  const FolderSelectItem = ({ name, iconName }) => (
    <div
      className={cn(
        name === "Delete" ? "text-destructive" : "",
        "flex items-center font-medium",
      )}
    >
      <IconComponent name={iconName} className="mr-2 w-4" />
      <span>{name}</span>
    </div>
  );

  const handleDoubleClick = (event, item) => {
    if (item.name === "My Projects") {
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

  const handleSelectChange = (option, folder) => {
    switch (option) {
      case "delete":
        handleDeleteFolder!(folder);
        break;
      case "download":
        handleDownloadFolder(folder.id!);
        break;
      case "rename":
        handleSelectFolderToRename(folder);
        break;
    }
  };

  const isMobile = useIsMobile({ maxWidth: 1024 });

  return (
    <Sidebar
      collapsible={isMobile ? "offcanvas" : "none"}
      data-testid="folder-sidebar"
    >
      <SidebarHeader className="p-4">
        <HeaderButtons />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="p-4 py-2">
          <SidebarGroupContent>
            <SidebarMenu>
              {!loading ? (
                folders.map((item, index) => {
                  const editFolderName = editFolders?.filter(
                    (folder) => folder.name === item.name,
                  )[0];
                  return (
                    <SidebarMenuItem>
                      <SidebarMenuButton
                        size="md"
                        onDragOver={(e) => dragOver(e, item.id!)}
                        onDragEnter={(e) => dragEnter(e, item.id!)}
                        onDragLeave={dragLeave}
                        onDrop={(e) => onDrop(e, item.id!)}
                        key={item.id}
                        data-testid={`sidebar-nav-${item.name}`}
                        isActive={checkPathName(item.id!)}
                        onClick={() => handleChangeFolder!(item.id!)}
                        className="group/menu-button"
                      >
                        <div
                          onDoubleClick={(event) => {
                            handleDoubleClick(event, item);
                          }}
                          className="flex w-full items-center justify-between gap-2"
                        >
                          <div className="flex flex-1 items-center gap-2">
                            {editFolderName?.edit && !isUpdatingFolder ? (
                              <Input
                                className="h-6 flex-1 focus:border-0"
                                onChange={(e) => {
                                  handleEditFolderName(e, item.name);
                                }}
                                ref={refInput}
                                onKeyDown={(e) => {
                                  handleKeyDownFn(e, item);
                                  handleKeyDown(e, e.key, "");
                                }}
                                autoFocus={true}
                                onBlur={(e) => {
                                  // fixes autofocus problem where cursor isn't present
                                  if (
                                    e.relatedTarget?.id ===
                                    `options-trigger-${item.name}`
                                  ) {
                                    refInput.current?.focus();
                                    return;
                                  }

                                  if (refInput.current?.value !== item.name) {
                                    handleEditNameFolder(item);
                                  } else {
                                    editFolderName.edit = false;
                                  }
                                  refInput.current?.blur();
                                }}
                                value={foldersNames[item.name]}
                                id={`input-folder-${item.name}`}
                                data-testid={`input-folder`}
                              />
                            ) : (
                              <span className="block w-0 grow truncate text-[13px] opacity-100">
                                {item.name}
                              </span>
                            )}
                          </div>
                          <Select
                            onValueChange={(value) =>
                              handleSelectChange(value, item)
                            }
                            value=""
                          >
                            <ShadTooltip
                              content="Options"
                              side="right"
                              styleClasses="z-50"
                            >
                              <SelectTrigger
                                className="w-fit"
                                id={`options-trigger-${item.name}`}
                                data-testid="more-options-button"
                              >
                                <IconComponent
                                  name={"MoreHorizontal"}
                                  className={`w-4 stroke-[1.5] px-0 text-muted-foreground group-hover/menu-button:block group-hover/menu-button:text-foreground ${
                                    checkPathName(item.id!) ? "block" : "hidden"
                                  }`}
                                />
                              </SelectTrigger>
                            </ShadTooltip>
                            <SelectContent
                              align="end"
                              alignOffset={-16}
                              position="popper"
                            >
                              {item.name !== "My Projects" && (
                                <SelectItem
                                  id="rename-button"
                                  value="rename"
                                  data-testid="btn-rename-folder"
                                >
                                  <FolderSelectItem
                                    name="Rename"
                                    iconName="SquarePen"
                                  />
                                </SelectItem>
                              )}
                              <SelectItem
                                value="download"
                                data-testid="btn-download-folder"
                              >
                                <FolderSelectItem
                                  name="Download Content"
                                  iconName="Download"
                                />
                              </SelectItem>
                              {index > 0 && (
                                <SelectItem
                                  value="delete"
                                  data-testid="btn-delete-folder"
                                >
                                  <FolderSelectItem
                                    name="Delete"
                                    iconName="Trash2"
                                  />
                                </SelectItem>
                              )}
                            </SelectContent>
                          </Select>
                        </div>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })
              ) : (
                <>
                  <SidebarFolderSkeleton />
                  <SidebarFolderSkeleton />
                </>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
};
export default SideBarFoldersButtonsComponent;
