import FolderSidebarNav from "@/components/folderSidebarComponent";
import { useDeleteFolders } from "@/controllers/API/queries/folders";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import ModalsComponent from "../components/modalsComponent";
import EmptyPage from "./emptyPage";

export default function CollectionPage(): JSX.Element {
  const location = useLocation();
  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const folders = useFolderStore((state) => state.folders);
  const showFolderModal = useFolderStore((state) => state.showFolderModal);
  const setShowFolderModal = useFolderStore(
    (state) => state.setShowFolderModal,
  );
  const queryClient = useQueryClient();

  const { data: folderData, isFetching } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
  });

  // cleanup the query cache when the component unmounts
  // prevent unnecessary queries on flow update
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
    <>
      <aside
        className={`flex w-2/6 min-w-[220px] max-w-[20rem] flex-col border-r bg-zinc-100 px-4 dark:bg-zinc-900 lg:inline ${
          showFolderModal ? "" : "hidden"
        }`}
      >
        <FolderSidebarNav
          handleChangeFolder={(id: string) => {
            navigate(`all/folder/${id}`);
          }}
          handleDeleteFolder={(item) => {
            setFolderToEdit(item);
            setOpenDeleteFolderModal(true);
          }}
        />
      </aside>

      {!isFetching ? (
        <div
          className={`relative mx-auto h-full w-full overflow-y-scroll ${
            showFolderModal ? "opacity-80 blur-[2px]" : ""
          }`}
          onClick={() => {
            if (showFolderModal) {
              setShowFolderModal(false);
            }
          }}
        >
          {folderData?.flows?.items?.length === 0 ? (
            <EmptyPage
              setOpenModal={setOpenModal}
              folderName={folderData?.folder?.name ?? ""}
            />
          ) : (
            <Outlet />
          )}
        </div>
      ) : (
        <LoadingPage />
      )}

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