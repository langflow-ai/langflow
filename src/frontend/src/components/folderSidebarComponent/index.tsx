import { useFolderStore } from "@/stores/foldersStore";
import { useIsFetching } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { FolderType } from "../../pages/MainPage/entities";
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
    <SideBarFoldersButtonsComponent
      handleChangeFolder={handleChangeFolder}
      handleDeleteFolder={handleDeleteFolder}
    />
  );
}
