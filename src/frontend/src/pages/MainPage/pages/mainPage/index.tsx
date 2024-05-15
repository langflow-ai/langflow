import { FolderPlusIcon } from "lucide-react";
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
import { downloadFlows } from "../../../../utils/reactflowUtils";
import ModalsComponent from "../../components/modalsComponent";
import useDeleteFolder from "../../hooks/delete-folder";
import useDropdownOptions from "../../hooks/dropdown-options";

const sidebarNavItems = [
  {
    title: "New Folder",
    icon: <FolderPlusIcon className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]" />,
  },
];

export default function HomePage(): JSX.Element {
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  const uploadFlows = useFlowsManagerStore((state) => state.uploadFlows);

  const location = useLocation();
  const pathname = location.pathname;
  const [openModal, setOpenModal] = useState(false);
  const [openFolderModal, setOpenFolderModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const is_component = pathname === "/components";
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useNavigate();

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

  const folders = useFolderStore((state) => state.folders);
  const folderId = location?.state?.folderId;
  const folderName = folders.find((folder) => folder.id === folderId)?.name;
  const folderDescription = folders.find(
    (folder) => folder.id === folderId
  )?.description;

  const { handleDeleteFolder } = useDeleteFolder({ getFoldersApi, navigate });

  return (
    <>
      <PageLayout
        title={!folderId ? USER_PROJECTS_HEADER : folderName!}
        description={!folderId ? MY_COLLECTION_DESC : folderDescription!}
        button={
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => {
                downloadFlows();
              }}
            >
              <IconComponent name="Download" className="main-page-nav-button" />
              Download Collection
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                uploadFlows();
              }}
            >
              <IconComponent name="Upload" className="main-page-nav-button" />
              Upload Collection
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
          <aside className="flex h-fit flex-col space-y-6  lg:w-1/4">
            <SidebarNav
              handleOpenNewFolderModal={() => {
                setFolderToEdit(null);
                setOpenFolderModal(true);
              }}
              items={sidebarNavItems}
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
