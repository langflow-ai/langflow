import LoadingComponent from "@/components/common/loadingComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import SideBarFoldersButtonsComponent from "@/components/core/folderSidebarComponent/components/sideBarFolderButtons";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useDeleteFolders } from "@/controllers/API/queries/folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import useFileDrop from "../hooks/use-on-file-drop";
import ModalsComponent from "../oldComponents/modalsComponent";
import EmptyPage from "./emptyPage";

export default function CollectionPage(): JSX.Element {
  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useCustomNavigate();
  const flows = useFlowsManagerStore((state) => state.flows);
  const examples = useFlowsManagerStore((state) => state.examples);
  const handleFileDrop = useFileDrop("flow");
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const folders = useFolderStore((state) => state.folders);
  const queryClient = useQueryClient();

  useEffect(() => {
    return () => queryClient.removeQueries({ queryKey: ["useGetFolder"] });
  }, []);

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
    <SidebarProvider width="280px">
      {flows &&
        examples &&
        folders &&
        (flows?.length !== examples?.length || folders?.length > 1) && (
          <SideBarFoldersButtonsComponent
            handleChangeFolder={(id: string) => {
              navigate(`all/folder/${id}`);
            }}
            handleDeleteFolder={(item) => {
              setFolderToEdit(item);
              setOpenDeleteFolderModal(true);
            }}
          />
        )}
      <main className="flex h-full w-full overflow-hidden">
        {flows && examples && folders ? (
          <div
            className={`relative mx-auto flex h-full w-full flex-col overflow-hidden`}
          >
            <CardsWrapComponent
              onFileDrop={handleFileDrop}
              dragMessage={`Drop your file(s) here`}
            >
              {flows?.length !== examples?.length || folders?.length > 1 ? (
                <Outlet />
              ) : (
                <EmptyPage setOpenModal={setOpenModal} />
              )}
            </CardsWrapComponent>
          </div>
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <LoadingComponent remSize={30} />
          </div>
        )}
      </main>
      <ModalsComponent
        openModal={openModal}
        setOpenModal={setOpenModal}
        openDeleteFolderModal={openDeleteFolderModal}
        setOpenDeleteFolderModal={setOpenDeleteFolderModal}
        handleDeleteFolder={handleDeleteFolder}
      />
    </SidebarProvider>
  );
}
