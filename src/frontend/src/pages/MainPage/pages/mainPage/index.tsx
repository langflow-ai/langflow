import { useDeleteFolders } from "@/controllers/API/queries/folders";
import useAlertStore from "@/stores/alertStore";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DropdownButton from "../../../../components/dropdownButtonComponent";
import PageLayout from "../../../../components/pageLayout";
import SidebarNav from "../../../../components/sidebarComponent";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../../../constants/constants";
import { useFolderStore } from "../../../../stores/foldersStore";
import ModalsComponent from "../../components/modalsComponent";
import useDropdownOptions from "../../hooks/use-dropdown-options";
import { getFolderById } from "../../services";

export default function HomePage(): JSX.Element {
  const location = useLocation();
  const pathname = location.pathname;
  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const is_component = pathname === "/components";
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useNavigate();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);

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
          getFolderById(myCollectionId!);
          getFoldersApi(true);
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
              onFirstBtnClick={() => setOpenModal(true)}
              options={dropdownOptions}
              plusButton={true}
              dropdownOptions={false}
            />
          </div>
        }
      >
        <div className="flex h-full w-full space-y-8 md:flex-col lg:flex-row lg:space-x-8 lg:space-y-0">
          <aside className="flex h-fit w-fit flex-col space-y-6">
            <SidebarNav
              items={[]}
              handleChangeFolder={(id: string) => {
                navigate(`all/folder/${id}`, { state: { folderId: id } });
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
