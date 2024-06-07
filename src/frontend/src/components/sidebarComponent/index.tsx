import { useLocation } from "react-router-dom";
import { FolderType } from "../../pages/MainPage/entities";
import { useFolderStore } from "../../stores/foldersStore";
import { cn } from "../../utils/utils";
import HorizontalScrollFadeComponent from "../horizontalScrollFadeComponent";
import SideBarButtonsComponent from "./components/sideBarButtons";
import SideBarFoldersButtonsComponent from "./components/sideBarFolderButtons";

type SidebarNavProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  handleChangeFolder?: (id: string) => void;
  handleEditFolder?: (item: FolderType) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  className?: string;
};

export default function SidebarNav({
  className,
  items,
  handleChangeFolder,
  handleEditFolder,
  handleDeleteFolder,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;
  const loadingFolders = useFolderStore((state) => state.loading);
  const folders = useFolderStore((state) => state.folders);

  const pathValues = ["folder", "components", "flows", "all"];
  const isFolderPath = pathValues.some((value) => pathname.includes(value));

  return (
    <nav className={cn(className)} {...props}>
      <HorizontalScrollFadeComponent>
        {items.length > 0 ? (
          <SideBarButtonsComponent items={items} pathname={pathname} />
        ) : (
          !loadingFolders &&
          folders?.length > 0 &&
          isFolderPath && (
            <SideBarFoldersButtonsComponent
              pathname={pathname}
              handleChangeFolder={handleChangeFolder}
              handleDeleteFolder={handleDeleteFolder}
            />
          )
        )}
      </HorizontalScrollFadeComponent>
    </nav>
  );
}
