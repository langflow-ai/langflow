import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DropdownButton from "../../../../components/dropdownButtonComponent";
import PageLayout from "../../../../components/pageLayout";
import SidebarNav from "../../../../components/sidebarComponent";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../../../constants/constants";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import ModalsComponent from "../../components/modalsComponent";
import useDeleteFolder from "../../hooks/use-delete-folder";
import useDropdownOptions from "../../hooks/use-dropdown-options";

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
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useNavigate();

  useEffect(() => {
    setCurrentFlowId("");
  }, [pathname]);

  const dropdownOptions = useDropdownOptions({
    uploadFlow,
    navigate,
    is_component,
  });

  const { handleDeleteFolder } = useDeleteFolder({ navigate });

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
          <div className="relative h-full w-full flex-1">
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
