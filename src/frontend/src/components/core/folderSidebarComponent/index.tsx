import { useLocation } from "react-router-dom";
import { FolderType } from "../../../pages/MainPage/entities";
import SideBarFoldersButtonsComponent from "./components/sideBarFolderButtons";

type SidebarNavProps = {
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  handleChangeFiles?: () => void;
  className?: string;
};

export default function FolderSidebarNav({
  className,
  handleChangeFolder,
  handleDeleteFolder,
  handleChangeFiles,
  ...props
}: SidebarNavProps) {
  const location = useLocation();

  return (
    <SideBarFoldersButtonsComponent
      handleChangeFolder={handleChangeFolder}
      handleDeleteFolder={handleDeleteFolder}
      handleChangeFiles={handleChangeFiles}
    />
  );
}
