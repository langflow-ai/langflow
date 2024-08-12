import { usePostDownloadMultipleFlows } from "@/controllers/API/queries/flows";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import { useEffect, useMemo, useState } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";
import { useLocation } from "react-router-dom";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import PaginatorComponent from "../../../../components/paginatorComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { FlowType } from "../../../../types/flow";
import useFileDrop from "../../hooks/use-on-file-drop";
import { getNameByType } from "../../utils/get-name-by-type";
import { sortFlows } from "../../utils/sort-flows";
import EmptyComponent from "../emptyComponent";
import HeaderComponent from "../headerComponent";
import CollectionCard from "./components/collectionCard";
import useDescriptionModal from "./hooks/use-description-modal";
import useFilteredFlows from "./hooks/use-filtered-flows";
import useDuplicateFlows from "./hooks/use-handle-duplicate";
import useSelectAll from "./hooks/use-handle-select-all";
import useSelectOptionsChange from "./hooks/use-select-options-change";
import useSelectedFlows from "./hooks/use-selected-flows";

export default function ComponentsComponent({
  type = "all",
}: {
  type?: string;
}) {
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const setAllFlows = useFlowsManagerStore((state) => state.setAllFlows);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);

  const flowsFromFolder = useFolderStore(
    (state) => state.selectedFolder?.flows,
  );

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [openDelete, setOpenDelete] = useState(false);
  const searchFlowsComponents = useFlowsManagerStore(
    (state) => state.searchFlowsComponents,
  );

  const setSelectedFlowsComponentsCards = useFlowsManagerStore(
    (state) => state.setSelectedFlowsComponentsCards,
  );

  const selectedFlowsComponentsCards = useFlowsManagerStore(
    (state) => state.selectedFlowsComponentsCards,
  );

  const handleFileDrop = useFileDrop(type);
  const [pageSize, setPageSize] = useState(20);
  const [pageIndex, setPageIndex] = useState(1);
  const location = useLocation();
  const all: FlowType[] = sortFlows(allFlows, type);
  const start = (pageIndex - 1) * pageSize;
  const end = start + pageSize;
  const data: FlowType[] = all?.slice(start, end);

  const name = getNameByType(type);

  const folderId = location?.state?.folderId;
  const getFolderById = useFolderStore((state) => state.getFolderById);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const setFolderUrl = useFolderStore((state) => state.setFolderUrl);
  const isLoadingFolders = useFolderStore((state) => state.isLoadingFolders);
  const setSelectedFolder = useFolderStore((state) => state.setSelectedFolder);

  const [shouldSelectAll, setShouldSelectAll] = useState(true);

  const cardTypes = useMemo(() => {
    if (window.location.pathname.includes("components")) {
      return "Components";
    }
    if (window.location.pathname.includes("flows")) {
      return "Flows";
    }
    return "Items";
  }, [window.location]);

  useEffect(() => {
    setFolderUrl(folderId ?? "");
    setSelectedFlowsComponentsCards([]);
    handleSelectAll(false);
    setShouldSelectAll(true);
    getFolderById(folderId ? folderId : myCollectionId);
  }, [location, folderId, myCollectionId]);

  useFilteredFlows(flowsFromFolder!, searchFlowsComponents, setAllFlows);

  const resetFilter = () => {
    setPageIndex(1);
    setPageSize(20);
  };

  const { getValues, control, setValue } = useForm();
  const entireFormValues = useWatch({ control });

  const methods = useForm();

  const { handleSelectAll } = useSelectAll(
    flowsFromFolder!,
    getValues,
    setValue,
  );

  const { handleDuplicate } = useDuplicateFlows(
    selectedFlowsComponentsCards,
    allFlows,
    resetFilter,
    getFoldersApi,
    folderId,
    myCollectionId!,
    getFolderById,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  );

  const { mutate: mutateDownloadMultipleFlows } =
    usePostDownloadMultipleFlows();

  const handleExport = () => {
    mutateDownloadMultipleFlows(
      {
        flow_ids: selectedFlowsComponentsCards,
      },
      {
        onSuccess: (data) => {
          const selectedFlow = allFlows.find(
            (flow) => flow.id === selectedFlowsComponentsCards[0],
          );

          const blobType =
            selectedFlowsComponentsCards.length > 1
              ? "application/zip"
              : "application/json";

          const fileNameSuffix =
            selectedFlowsComponentsCards.length > 1
              ? "_langflow_flows.zip"
              : `${selectedFlow!.name}.json`;

          const blob = new Blob([data], { type: blobType });

          const link = document.createElement("a");
          link.href = window.URL.createObjectURL(blob);

          let current_time = new Date().toISOString().replace(/[:.]/g, "");

          current_time = current_time
            .replace(/-/g, "")
            .replace(/T/g, "")
            .replace(/Z/g, "");

          link.download =
            selectedFlowsComponentsCards.length > 1
              ? `${current_time}${fileNameSuffix}`
              : `${fileNameSuffix}`;

          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          setSuccessData({ title: `${cardTypes} exported successfully` });
          setSelectedFlowsComponentsCards([]);
          handleSelectAll(false);
          setShouldSelectAll(true);
        },
      },
    );
  };

  const { handleSelectOptionsChange } = useSelectOptionsChange(
    selectedFlowsComponentsCards,
    setErrorData,
    setOpenDelete,
    handleDuplicate,
    handleExport,
  );

  const deleteFlow = useDeleteFlow();

  const handleDeleteMultiple = () => {
    deleteFlow({ id: selectedFlowsComponentsCards })
      .then(() => {
        setAllFlows([]);
        setSelectedFolder(null);
        resetFilter();
        getFoldersApi(true);
        if (!folderId || folderId === myCollectionId) {
          getFolderById(folderId ? folderId : myCollectionId);
        }
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch((e) => {
        setErrorData({
          title: "Error deleting items",
          list: ["Please try again"],
        });
      });
  };

  useSelectedFlows(entireFormValues, setSelectedFlowsComponentsCards);

  const descriptionModal = useDescriptionModal(
    selectedFlowsComponentsCards,
    type,
  );

  const getTotalRowsCount = () => {
    if (type === "all") return allFlows?.length;

    return allFlows?.filter(
      (f) => (f.is_component ?? false) === (type === "component"),
    )?.length;
  };

  return (
    <>
      <div className="flex w-full gap-4 pb-5">
        {allFlows?.length > 0 && (
          <HeaderComponent
            shouldSelectAll={shouldSelectAll}
            setShouldSelectAll={setShouldSelectAll}
            handleDelete={() => handleSelectOptionsChange("delete")}
            handleSelectAll={handleSelectAll}
            handleDuplicate={() => handleSelectOptionsChange("duplicate")}
            handleExport={() => handleSelectOptionsChange("export")}
            disableFunctions={!(selectedFlowsComponentsCards?.length > 0)}
          />
        )}
      </div>

      <CardsWrapComponent
        onFileDrop={handleFileDrop}
        dragMessage={`Drag your ${name} here`}
      >
        <div
          className="flex h-full w-full flex-col justify-between"
          data-testid="cards-wrapper"
        >
          <div className="flex w-full flex-col gap-4">
            {!isLoading && !isLoadingFolders && data?.length === 0 ? (
              <EmptyComponent />
            ) : (
              <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-2">
                {isLoading === false &&
                data?.length > 0 &&
                isLoadingFolders === false ? (
                  <>
                    {data?.map((item) => (
                      <FormProvider {...methods} key={item.id}>
                        <form>
                          <CollectionCard
                            item={item}
                            type={type}
                            isLoading={isLoading}
                            control={control}
                          />
                        </form>
                      </FormProvider>
                    ))}
                  </>
                ) : (
                  <>
                    <SkeletonCardComponent />
                    <SkeletonCardComponent />
                  </>
                )}
              </div>
            )}
          </div>
          {!isLoading && data?.length > 0 && (
            <div className="relative py-6">
              <PaginatorComponent
                storeComponent={true}
                pageIndex={pageIndex}
                pageSize={pageSize}
                rowsCount={[10, 20, 50, 100]}
                totalRowsCount={getTotalRowsCount()}
                paginate={(pageSize, pageIndex) => {
                  setPageIndex(pageIndex);
                  setPageSize(pageSize);
                }}
              ></PaginatorComponent>
            </div>
          )}
        </div>
      </CardsWrapComponent>
      {openDelete && (
        <DeleteConfirmationModal
          open={openDelete}
          setOpen={setOpenDelete}
          onConfirm={handleDeleteMultiple}
          description={descriptionModal}
        >
          <></>
        </DeleteConfirmationModal>
      )}
    </>
  );
}
