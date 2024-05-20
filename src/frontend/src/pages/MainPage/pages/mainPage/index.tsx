import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DropdownButton from "../../../../components/dropdownButtonComponent";
import IconComponent from "../../../../components/genericIconComponent";
import PageLayout from "../../../../components/pageLayout";
import SidebarNav from "../../../../components/sidebarComponent";
import { Button } from "../../../../components/ui/button";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../../../constants/constants";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import ModalsComponent from "../../components/modalsComponent";
import useDeleteFolder from "../../hooks/use-delete-folder";
import useDropdownOptions from "../../hooks/use-dropdown-options";

import useAlertStore from "../../../../stores/alertStore";
import { handleDownloadFolderFn } from "../../utils/handle-download-folder";

export default function HomePage(): JSX.Element {
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId,
  );

  const location = useLocation();
  const pathname = location.pathname;
  const [openModal, setOpenModal] = useState(false);
  const [openFolderModal, setOpenFolderModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const is_component = pathname === "/components";
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const uploadFolder = useFolderStore((state) => state.uploadFolder);
  const navigate = useNavigate();
  const folders = useFolderStore((state) => state.folders);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folderId = location?.state?.folderId || myCollectionId;
  const folderName = folders.find((folder) => folder.id === folderId)?.name;
  const folderDescription = folders.find(
    (folder) => folder.id === folderId,
  )?.description;

  useEffect(() => {
    getFoldersApi();
  }, []);

  useEffect(() => {
    setCurrentFlowId("");
  }, [pathname]);

  const dropdownOptions = useDropdownOptions({
    uploadFlow,
    navigate,
    is_component,
  });

  const { handleDeleteFolder } = useDeleteFolder({ getFoldersApi, navigate });

  const handleDownloadFolder = () => {
    if (allFlows.length === 0) {
      setErrorData({
        title: "Folder is empty",
        list: [],
      });
      return;
    }
    handleDownloadFolderFn(folderId);
  };

  const handleUploadFlowsToFolder = () => {
    uploadFolder(folderId);
  };

  return (
    <>
      <PageLayout
        title={USER_PROJECTS_HEADER}
        description={MY_COLLECTION_DESC}
        button={
          <div className="flex gap-2">
            <Button variant="primary" onClick={handleDownloadFolder}>
              <IconComponent name="Download" className="main-page-nav-button" />
              Download Folder
            </Button>
            <Button variant="primary" onClick={handleUploadFlowsToFolder}>
              <IconComponent name="Upload" className="main-page-nav-button" />
              Upload Folder
            </Button>
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
              handleOpenNewFolderModal={() => {
                setFolderToEdit(null);
                setOpenFolderModal(true);
              }}
              items={[]}
              handleChangeFolder={(id: string) => {
                navigate(`flows/folder/${id}`, { state: { folderId: id } });
              }}
              handleEditFolder={(item) => {
                setFolderToEdit(item);
                setOpenFolderModal(true);
              }}
              handleDeleteFolder={(item) => {
                setFolderToEdit(item);
                setOpenDeleteFolderModal(true);
              }}
              className="w-[20vw]"
            />
          </aside>
          <div className="h-full w-full flex-1">
            <Outlet />
          </div>
        </div>
      </PageLayout>
      <ModalsComponent
        openModal={openModal}
        setOpenModal={setOpenModal}
        openFolderModal={openFolderModal}
        setOpenFolderModal={setOpenFolderModal}
        openDeleteFolderModal={openDeleteFolderModal}
        setOpenDeleteFolderModal={setOpenDeleteFolderModal}
        handleDeleteFolder={handleDeleteFolder}
      />
    </>
  );
}
