import { useLocation } from "react-router-dom";
import { FolderType } from "../../../../pages/MainPage/entities";
import { useFolderStore } from "../../../../stores/foldersStore";
import { cn } from "../../../../utils/utils";
import DropdownButton from "../../../dropdownButtonComponent";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../genericIconComponent";
import { Button, buttonVariants } from "../../../ui/button";
import useFileDrop from "../../hooks/use-on-file-drop";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { handleDownloadFolderFn } from "../../../../pages/MainPage/utils/handle-download-folder";
import useAlertStore from "../../../../stores/alertStore";

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
  const uploadFolder = useFolderStore((state) => state.uploadFolder);
  const currentFolder = pathname.split("/");
  const urlWithoutPath = pathname.split("/").length < 4;
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId) {
      return true;
    }
    return currentFolder.includes(itemId);
  };
  const location = useLocation();
  const folderId = location?.state?.folderId ?? myCollectionId;
  const getFolderById = useFolderStore((state) => state.getFolderById);

  const handleFolderChange = (folderId: string) => {
    getFolderById(folderId);
  };

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(
    folderId,
    handleFolderChange,
  );

  const handleUploadFlowsToFolder = () => {
    uploadFolder(folderId);
  };

  const handleDownloadFolder = (id: string) => {
    handleDownloadFolderFn(id);
  };

  return (
    <>
      <div className="flex shrink-0 items-center justify-between">
        <DropdownButton
          firstButtonName="New Folder"
          onFirstBtnClick={handleAddFolder!}
          options={[]}
          plusButton={true}
          dropdownOptions={false}
        />
        <Button
          variant="primary"
          onClick={handleUploadFlowsToFolder}
          className="px-7"
        >
          <ForwardedIconComponent
            name="Upload"
            className="main-page-nav-button"
          />
          Upload
        </Button>
      </div>

      <div className="flex gap-2 overflow-auto lg:h-[70vh] lg:flex-col">
        <>
          {folders.map((item, index) => (
            <div
              onDragOver={dragOver}
              onDragEnter={dragEnter}
              onDragLeave={dragLeave}
              onDrop={(e) => onDrop(e, item.id!)}
              key={item.id}
              data-testid={`sidebar-nav-${item.name}`}
              className={cn(
                buttonVariants({ variant: "ghost" }),
                checkPathName(item.id!)
                  ? "border border-border bg-muted hover:bg-muted"
                  : "border hover:bg-transparent lg:border-transparent lg:hover:border-border",
                "group flex w-full shrink-0 cursor-pointer gap-2 opacity-100 lg:min-w-full",
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
                )}
                {index > 0 && (
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
                )}
                <Button
                  className="hidden p-0 hover:bg-white group-hover:block hover:dark:bg-[#0c101a00]"
                  onClick={(e) => {
                    handleDownloadFolder(item.id!);
                    e.stopPropagation();
                    e.preventDefault();
                  }}
                  variant={"ghost"}
                >
                  <IconComponent
                    name={"Download"}
                    className="  w-4 stroke-[1.5] text-white  "
                  />
                </Button>
              </div>
            </div>
          ))}
        </>
      </div>
    </>
  );
};
export default SideBarFoldersButtonsComponent;
