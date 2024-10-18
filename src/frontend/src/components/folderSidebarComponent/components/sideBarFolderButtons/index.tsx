import ShadTooltip from "@/components/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
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
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { FolderType } from "../../../../pages/MainPage/entities";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { handleKeyDown } from "../../../../utils/reactflowUtils";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button, buttonVariants } from "../../../ui/button";
import { Input } from "../../../ui/input";
import useFileDrop from "../../hooks/use-on-file-drop";
import { SidebarFolderSkeleton } from "../sidebarFolderSkeleton";

type SideBarFoldersButtonsComponentProps = {
  pathname: string;
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  folders: FolderType[] | undefined;
  loading?: boolean;
};
const SideBarFoldersButtonsComponent = ({
  pathname,
  handleChangeFolder,
  handleDeleteFolder,
  folders = [],
  loading,
}: SideBarFoldersButtonsComponentProps) => {
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
  const folderIdDragging = useFolderStore((state) => state.folderIdDragging);

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
                    title: `Error on upload`,
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
          const folder = folders.find((f) => f.id === data.folderId);

          data.folder_name = folder?.name || "folder";
          data.folder_description = folder?.description || "";

          const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
            JSON.stringify(data),
          )}`;

          const link = document.createElement("a");
          link.href = jsonString;
          link.download = `${data.folder_name}.json`;

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
    mutateAddFolder({
      data: {
        name: "New Folder",
        parent_id: null,
        description: "",
      },
    });
    track("Create New Folder");
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

  const isFetchingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

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
    <div className="mt-4 flex shrink-0 items-center justify-between gap-2">
      <div className="text-md flex-1 font-semibold">Folders</div>
      <UploadFolderButton
        onClick={handleUploadFlowsToFolder}
        disabled={isUpdatingFolder}
      />
      <AddFolderButton onClick={addNewFolder} disabled={isUpdatingFolder} />
    </div>
  );

  const AddFolderButton = ({ onClick, disabled }) => (
    <ShadTooltip content="Add a new folder">
      <Button
        variant="primary"
        size="icon"
        className="border-0"
        onClick={onClick}
        data-testid="add-folder-button"
        disabled={disabled}
      >
        <IconComponent name="Plus" className="w-5" />
      </Button>
    </ShadTooltip>
  );

  const UploadFolderButton = ({ onClick, disabled }) => (
    <ShadTooltip content="Upload a folder">
      <Button
        variant="primary"
        size="icon"
        className="border-0"
        onClick={onClick}
        data-testid="upload-folder-button"
        disabled={disabled}
      >
        <IconComponent name="Upload" className="w-4" />
      </Button>
    </ShadTooltip>
  );

  const FolderSelectItem = ({ name, iconName }) => (
    <div
      className={cn(
        name === "Delete" ? "text-error" : "",
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

  return (
    <>
      <HeaderButtons />

      <div className="flex gap-2 overflow-auto lg:h-[70vh] lg:flex-col">
        <>
          {!loading ? (
            folders.map((item, index) => {
              const editFolderName = editFolders?.filter(
                (folder) => folder.name === item.name,
              )[0];
              return (
                <div
                  onDragOver={(e) => dragOver(e, item.id!)}
                  onDragEnter={(e) => dragEnter(e, item.id!)}
                  onDragLeave={dragLeave}
                  onDrop={(e) => onDrop(e, item.id!)}
                  key={item.id}
                  data-testid={`sidebar-nav-${item.name}`}
                  className={cn(
                    buttonVariants({ variant: "ghost" }),
                    checkPathName(item.id!)
                      ? "bg-muted hover:bg-muted"
                      : "border hover:bg-transparent lg:border-transparent lg:hover:border-border",
                    "group flex w-full shrink-0 cursor-pointer gap-2 opacity-100 lg:min-w-full",
                    folderIdDragging === item.id! ? "bg-border" : "",
                  )}
                  onClick={() => handleChangeFolder!(item.id!)}
                >
                  <div
                    onDoubleClick={(event) => {
                      handleDoubleClick(event, item);
                    }}
                    className="flex w-full items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <IconComponent
                        name={"folder"}
                        className="mr-2 w-4 flex-shrink-0 justify-start stroke-[1.5] opacity-100"
                      />
                      {editFolderName?.edit && !isUpdatingFolder ? (
                        <div>
                          <Input
                            className="w-36"
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
                        </div>
                      ) : (
                        <span className="block w-full grow truncate opacity-100">
                          {item.name}
                        </span>
                      )}
                    </div>
                    <Select
                      onValueChange={(value) => handleSelectChange(value, item)}
                      value=""
                    >
                      <SelectTrigger
                        className="w-fit"
                        id={`options-trigger-${item.name}`}
                        data-testid="more-options-button"
                      >
                        <IconComponent
                          name={"MoreHorizontal"}
                          className="hidden w-4 stroke-[1.5] px-0 text-primary group-hover:block"
                        />
                      </SelectTrigger>
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
                              iconName="square-pen"
                            />
                          </SelectItem>
                        )}
                        <SelectItem
                          value="download"
                          data-testid="btn-download-folder"
                        >
                          <FolderSelectItem
                            name="Download Content"
                            iconName="download"
                          />
                        </SelectItem>
                        {index > 0 && (
                          <SelectItem
                            value="delete"
                            data-testid="btn-delete-folder"
                          >
                            <FolderSelectItem name="Delete" iconName="trash" />
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              );
            })
          ) : (
            <>
              <SidebarFolderSkeleton />
              <SidebarFolderSkeleton />
            </>
          )}
        </>
      </div>
    </>
  );
};
export default SideBarFoldersButtonsComponent;
