import { useLocation } from "react-router-dom";
import { FolderType } from "../../../../pages/MainPage/entities";
import { useFolderStore } from "../../../../stores/foldersStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { cn } from "../../../../utils/utils";
import DropdownButton from "../../../dropdownButtonComponent";
import IconComponent from "../../../genericIconComponent";
import { Button, buttonVariants } from "../../../ui/button";
import useFileDrop from "../../hooks/use-on-file-drop";

type SideBarFoldersButtonsComponentProps = {
  folders: FolderType[];
  pathname: string;
  handleChangeFolder?: (id: string) => void;
  handleEditFolder?: (item: FolderType) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  handleAddFolder?: () => void;
};
const SideBarFoldersButtonsComponent = ({
  folders,
  pathname,
  handleAddFolder,
  handleChangeFolder,
  handleEditFolder,
  handleDeleteFolder,
}: SideBarFoldersButtonsComponentProps) => {
  const currentFolder = pathname.split("/");
  const urlWithoutPath = pathname.split("/").length < 4;
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const hasStore = useStoreStore((state) => state.hasStore);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);

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
    handleFolderChange,
  );

  return (
    <>
      <div className="shrink-0">
        <DropdownButton
          firstButtonName="New Folder"
          onFirstBtnClick={handleAddFolder!}
          options={[]}
          plusButton={true}
          dropdownOptions={false}
        />
      </div>

      <div className="flex h-[70vh] gap-2 overflow-auto lg:flex-col">
        <>
          {folders.map((item, index) => (
            <div
              onDragOver={dragOver}
              onDragEnter={dragEnter}
              onDragLeave={dragLeave}
              onDrop={onDrop}
              key={item.id}
              data-testid={`sidebar-nav-${item.name}`}
              className={cn(
                `${folderDragging ? "hover:bg-red-500" : ""}`,
                buttonVariants({ variant: "ghost" }),
                checkPathName(item.id!)
                  ? "border border-border bg-muted hover:bg-muted"
                  : "border hover:bg-transparent lg:border-transparent lg:hover:border-border",
                "group flex min-w-48 max-w-48 shrink-0 cursor-pointer gap-2 opacity-100 lg:min-w-full",
              )}
              onClick={() => handleChangeFolder!(item.id!)}
            >
              <div className="flex w-full items-center gap-2">
                <IconComponent
                  name={"folder"}
                  className="mr-2 w-4 flex-shrink-0 justify-start stroke-[1.5] opacity-100"
                />
                <span className="block max-w-full truncate opacity-100">
                  {item.name}
                </span>
                <div className="flex-1" />
                {index > 0 && (
                  <>
                    <Button
                      className="hidden p-0 hover:bg-white group-hover:block hover:dark:bg-[#0c101a00]"
                      onClick={(e) => {
                        handleDeleteFolder!(item);
                        e.stopPropagation();
                        e.preventDefault();
                      }}
                      variant={"ghost"}
                    >
                      <IconComponent
                        name={"trash"}
                        className=" w-4 stroke-[1.5]"
                      />
                    </Button>

                    <Button
                      className="hidden p-0 hover:bg-white group-hover:block hover:dark:bg-[#0c101a00]"
                      onClick={(e) => {
                        handleEditFolder!(item);
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
            </div>
          ))}
        </>
      </div>
    </>
  );
};
export default SideBarFoldersButtonsComponent;
