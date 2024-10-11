import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useFolderStore } from "@/stores/foldersStore";
import { useIsFetching } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { FolderType } from "../../pages/MainPage/entities";
import { cn } from "../../utils/utils";
import HorizontalScrollFadeComponent from "../horizontalScrollFadeComponent";
import SideBarFoldersButtonsComponent from "./components/sideBarFolderButtons";

type SidebarNavProps = {
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  className?: string;
};

export default function FolderSidebarNav({
  className,
  handleChangeFolder,
  handleDeleteFolder,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;
  const folders = useFolderStore((state) => state.folders);

  const isPending = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  return (
    <nav className={cn(className)} {...props}>
      <HorizontalScrollFadeComponent>
        <SideBarFoldersButtonsComponent
          loading={isPending || !folders}
          pathname={pathname}
          handleChangeFolder={handleChangeFolder}
          handleDeleteFolder={handleDeleteFolder}
          folders={folders}
        />
      </HorizontalScrollFadeComponent>
    </nav>
  );
}
