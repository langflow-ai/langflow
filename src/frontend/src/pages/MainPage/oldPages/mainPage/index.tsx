import FolderSidebarNav from "@/components/core/folderSidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useDeleteFolders } from "@/controllers/API/queries/folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import PageLayout from "../../../../components/common/pageLayout";
import DropdownButton from "../../../../components/core/dropdownButtonComponent";
import {
  MY_COLLECTION_DESC,
  USER_PROJECTS_HEADER,
} from "../../../../constants/constants";
import { useFolderStore } from "../../../../stores/foldersStore";
import useDropdownOptions from "../../hooks/use-dropdown-options";
import ModalsComponent from "../../oldComponents/modalsComponent";

export default function OldHomePage(): JSX.Element {
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
  const queryClient = useQueryClient();

  // cleanup the query cache when the component unmounts
  // prevent unnecessary queries on flow update
  useEffect(() => {
    return () => queryClient.removeQueries({ queryKey: ["useGetFolder"] });
  }, []);

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

  const isFetchingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  const isFetchingFolder = !!useIsFetching({
    queryKey: ["useGetFolder"],
    exact: false,
  });

  const isLoadingFolder = isFetchingFolders || isFetchingFolder;

  return (
    <>
      <div className="flex h-full w-full space-y-8 md:flex-col lg:flex-row lg:space-y-0">
        <SidebarProvider>
          <aside className="hidden h-full w-fit flex-col space-y-6 px-4 lg:flex">
            <FolderSidebarNav
              handleChangeFolder={(id: string) => {
                navigate(`all/folder/${id}`);
              }}
              handleDeleteFolder={(item) => {
                setFolderToEdit(item);
                setOpenDeleteFolderModal(true);
              }}
              className="w-[20vw] max-w-[288px]"
            />
          </aside>
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
                  isFetchingFolders={isLoadingFolder}
                />
              </div>
            }
          >
            <div className="relative h-full w-full flex-1">
              <Outlet />
            </div>
          </PageLayout>
        </SidebarProvider>
      </div>
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
