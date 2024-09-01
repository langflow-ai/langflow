import FolderSidebarNav from "@/components/folderSidebarComponent";
import { useDeleteFolders } from "@/controllers/API/queries/folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import DropdownButton from "../../../../components/dropdownButtonComponent";
import PageLayout from "../../../../components/pageLayout";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../../../constants/constants";
import { useFolderStore } from "../../../../stores/foldersStore";
import ModalsComponent from "../../components/modalsComponent";
import useDropdownOptions from "../../hooks/use-dropdown-options";

export default function HomePage(): JSX.Element {
  const location = useLocation();
  const pathname = location.pathname;
  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const is_component = pathname.includes("/components");
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useCustomNavigate();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);

  const dropdownOptions = useDropdownOptions({
    navigate,
    is_component,
  });

  const { mutate } = useDeleteFolders();

  const handleDeleteFolder = () => {
    mutate(
      {
        folder_id: folderToEdit?.id!,
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: "Folder deleted successfully.",
          });
          navigate("/all");
        },
        onError: (err) => {
          console.error(err);
          setErrorData({
            title: "Error deleting folder.",
          });
        },
      },
    );
  };

  return (
    <>
      <PageLayout
        title={USER_PROJECTS_HEADER}
        description={MY_COLLECTION_DESC}
        button={
          <div className="flex gap-2">
            <DropdownButton
              firstButtonName="New Project"
              onFirstBtnClick={() => {
                setOpenModal(true);
                track("New Project Button Clicked");
              }}
              options={dropdownOptions}
              plusButton={true}
              dropdownOptions={false}
            />
          </div>
        }
      >
        <div className="flex h-full w-full space-y-8 md:flex-col lg:flex-row lg:space-x-8 lg:space-y-0">
          <aside className="flex h-fit w-fit flex-col space-y-6">
            <FolderSidebarNav
              handleChangeFolder={(id: string) => {
                navigate(`all/folder/${id}`);
              }}
              handleDeleteFolder={(item) => {
                setFolderToEdit(item);
                setOpenDeleteFolderModal(true);
              }}
              className="w-[20vw]"
            />
          </aside>
          <div className="relative h-full w-full flex-1">
            <Outlet />
          </div>
        </div>
      </PageLayout>
      <ModalsComponent
        openModal={openModal}
        setOpenModal={setOpenModal}
        openDeleteFolderModal={openDeleteFolderModal}
        setOpenDeleteFolderModal={setOpenDeleteFolderModal}
        handleDeleteFolder={handleDeleteFolder}
      />
    </>
  );
}
