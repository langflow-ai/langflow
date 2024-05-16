import { useLocation } from "react-router-dom";
import { FolderType } from "../../pages/MainPage/entities";
import { useFolderStore } from "../../stores/foldersStore";
import { cn } from "../../utils/utils";
import SideBarButtonsComponent from "./components/sideBarButtons";
import SideBarFoldersButtonsComponent from "./components/sideBarFolderButtons";

type SidebarNavProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  handleOpenNewFolderModal: () => void;
  handleChangeFolder: (id: string) => void;
  handleEditFolder: (item: FolderType) => void;
  handleDeleteFolder: (item: FolderType) => void;
  className?: string;
};

export default function SidebarNav({
  className,
  items,
  handleOpenNewFolderModal,
  handleChangeFolder,
  handleEditFolder,
  handleDeleteFolder,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;
  const loadingFolders = useFolderStore((state) => state.loading);
  const folders = useFolderStore((state) => state.folders);

  const pathValues = ["folder", "components", "flows"];
  const isFolderPath = pathValues.some((value) => pathname.includes(value));

  return (
    <nav
      className={cn(
        "flex space-x-2 lg:flex-col lg:space-x-0 lg:space-y-1",
        className
      )}
      {...props}
    >
      <SideBarButtonsComponent
        items={items}
        pathname={pathname}
        handleOpenNewFolderModal={handleOpenNewFolderModal}
      />

      {!loadingFolders && folders?.length > 0 && isFolderPath && (
        <>
          <SideBarFoldersButtonsComponent
            folders={folders}
            pathname={pathname}
            handleChangeFolder={handleChangeFolder}
            handleEditFolder={handleEditFolder}
            handleDeleteFolder={handleDeleteFolder}
            handleAddFolder={handleOpenNewFolderModal}
          />
        </>
      )}
    </nav>
  );
}
