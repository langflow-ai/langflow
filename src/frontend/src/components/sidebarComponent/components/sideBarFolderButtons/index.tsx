import { FolderType } from "../../../../pages/MainPage/entities";
import { useFolderStore } from "../../../../stores/foldersStore";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button, buttonVariants } from "../../../ui/button";

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
        >
          <div className="mr-auto flex">
            <IconComponent
              name={"folder"}
              className="mr-2 w-4 justify-start stroke-[1.5] opacity-100"
            />
            <span className="self-center opacity-100">{item.name}</span>
          </div>

          {index > 0 && (
            <>
              <Button
                className="invisible p-0 hover:bg-white group-hover:visible hover:dark:bg-[#0c101a00]"
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
