import CardsWrapComponent from "@/components/cardsWrapComponent";
import FolderSidebarNav from "@/components/folderSidebarComponent";
import { useDeleteFolders } from "@/controllers/API/queries/folders";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { PaginatedFolderType } from "../entities";
import useFileDrop from "../hooks/use-on-file-drop";
import ModalsComponent from "../oldComponents/modalsComponent";
import EmptyPage from "./emptyPage";

export default function CollectionPage(): JSX.Element {
  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const setFolderToEdit = useFolderStore((state) => state.setFolderToEdit);
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const handleFileDrop = useFileDrop("flow");
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const showFolderModal = useFolderStore((state) => state.showFolderModal);
  const folders = useFolderStore((state) => state.folders);
  const setShowFolderModal = useFolderStore(
    (state) => state.setShowFolderModal,
  );
  const queryClient = useQueryClient();

  useEffect(() => {
    return () => queryClient.removeQueries({ queryKey: ["useGetFolder"] });
  }, []);

  const { isFetching, data } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
  });

  const [folderData, setFolderData] = useState<PaginatedFolderType | null>(
    null,
  );

  useEffect(() => {
    setFolderData(data ?? null);
  }, [data]);

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
      {(folderData?.flows?.items?.length !== 0 || folders?.length > 1) && (
        <aside
          className={`flex w-2/6 min-w-[220px] max-w-[20rem] flex-col border-r bg-background px-4 lg:inline ${
            showFolderModal ? "" : "hidden"
          }`}
        >
          <FolderSidebarNav
            handleChangeFolder={(id: string) => {
              navigate(`all/folder/${id}`);
              setShowFolderModal(false);
            }}
            handleDeleteFolder={(item) => {
              setFolderToEdit(item);
              setOpenDeleteFolderModal(true);
            }}
          />
        </aside>
      )}

      {!isFetching && folderData ? (
        <div
          className={`relative mx-auto h-full w-full overflow-y-scroll ${
            showFolderModal ? "opacity-80 blur-[2px]" : ""
          }`}
          onClick={(e) => {
            e.stopPropagation();

            if (showFolderModal) {
              setShowFolderModal(false);
            }
          }}
        >
          <CardsWrapComponent
            onFileDrop={handleFileDrop}
            dragMessage={`Drop your file(s) here`}
          >
            {folderData && folderData?.flows?.items?.length !== 0 ? (
              <Outlet />
            ) : (
              <EmptyPage
                setOpenModal={setOpenModal}
                setShowFolderModal={setShowFolderModal}
                folderData={folderData}
              />
            )}
          </CardsWrapComponent>
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
