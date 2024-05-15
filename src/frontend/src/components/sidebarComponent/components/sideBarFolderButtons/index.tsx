import { useLocation } from "react-router-dom";
import { FolderType } from "../../../../pages/MainPage/entities";
import { useFolderStore } from "../../../../stores/foldersStore";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button, buttonVariants } from "../../../ui/button";
import useFileDrop from "../../hooks/use-on-file-drop";

type SideBarFoldersButtonsComponentProps = {
  folders: FolderType[];
  pathname: string;
  handleChangeFolder: (id: string) => void;
  handleEditFolder: (item: FolderType) => void;
  handleDeleteFolder: (item: FolderType) => void;
};
const SideBarFoldersButtonsComponent = ({
  folders,
  pathname,
  handleChangeFolder,
  handleEditFolder,
  handleDeleteFolder,
}: SideBarFoldersButtonsComponentProps) => {
  const currentFolder = pathname.split("/");
  const urlWithoutPath = pathname.split("/").length < 4;

  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId) {
      return true;
    }
    return currentFolder.includes(itemId);
  };
  const location = useLocation();
  const folderId = location?.state?.folderId ?? myCollectionId;
  const is_component = location?.pathname.includes("components");
  const folderDragging = useFolderStore((state) => state.folderDragging);
  const getFolderById = useFolderStore((state) => state.getFolderById);

  const handleFolderChange = (folderId: string) => {
    getFolderById(folderId);
  };

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(
    folderId,
    is_component,
    handleFolderChange
  );

  return (
    <>
      {folders.map((item, index) => (
        <div
          key={item.id}
          data-testid={`sidebar-nav-${item.name}`}
          className={cn(
            buttonVariants({ variant: "ghost" }),
            checkPathName(item.id!)
              ? "border border-border bg-muted hover:bg-muted"
              : "border border-transparent hover:border-border hover:bg-transparent",
            "group flex cursor-pointer gap-2 opacity-100"
          )}
          onClick={() => handleChangeFolder(item.id!)}
          onDragOver={(e) => dragOver(e, item.id!)}
          onDragEnter={(e) => dragEnter(e, item.id!)}
          onDragLeave={dragLeave}
          onDrop={onDrop}
        >
          <div className="mr-auto flex">
            {folderDragging !== item?.id && (
              <IconComponent
                name={"folder"}
                className="mr-2 w-4 justify-start stroke-[1.5] opacity-100"
              />
            )}

            <div className="lg:max-w-[120px] xl:max-w-[200px] ">
              <span className="block max-w-full truncate opacity-100">
                {folderDragging === item?.id ? (
                  <div className="flex">
                    <IconComponent
                      name={"upload"}
                      className="mr-2 w-4 justify-start stroke-[1.5] opacity-100"
                    />
                    <span className="self-center">Drop to upload</span>
                  </div>
                ) : (
                  item.name
                )}
              </span>
            </div>
          </div>

          {index > 0 && (
            <>
              <Button
                className="invisible  p-0 hover:bg-white group-hover:visible hover:dark:bg-[#0c101a00]"
                onClick={(e) => {
                  handleDeleteFolder(item);
                  e.stopPropagation();
                  e.preventDefault();
                }}
                variant={"ghost"}
              >
                <IconComponent name={"trash"} className=" w-4 stroke-[1.5]" />
              </Button>

              <Button
                className="invisible p-0 hover:bg-white group-hover:visible hover:dark:bg-[#0c101a00]"
                onClick={(e) => {
                  handleEditFolder(item);
                  e.stopPropagation();
                  e.preventDefault();
                }}
                variant={"ghost"}
              >
                <IconComponent
                  name={"pencil"}
                  className="  w-4 stroke-[1.5] text-white  "
                />
              </Button>
            </>
          )}
        </div>
      ))}
    </>
  );
};
export default SideBarFoldersButtonsComponent;
