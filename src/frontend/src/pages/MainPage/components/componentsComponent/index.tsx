import { useEffect, useMemo, useState } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import CollectionCardComponent from "../../../../components/cardComponent";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import IconComponent from "../../../../components/genericIconComponent";
import PaginatorComponent from "../../../../components/paginatorComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import { Button } from "../../../../components/ui/button";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";
import useAlertStore from "../../../../stores/alertStore";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { FlowType } from "../../../../types/flow";
import { downloadFlow, removeApiKeys } from "../../../../utils/reactflowUtils";
import useFileDrop from "../../hooks/use-on-file-drop";
import { getNameByType } from "../../utils/get-name-by-type";
import { sortFlows } from "../../utils/sort-flows";
import EmptyComponent from "../emptyComponent";
import HeaderComponent from "../headerComponent";
import useDeleteMultipleFlows from "./hooks/use-delete-multiple";
import useDescriptionModal from "./hooks/use-description-modal";
import useFilteredFlows from "./hooks/use-filtered-flows";
import useDuplicateFlows from "./hooks/use-handle-duplicate";
import useExportFlows from "./hooks/use-handle-export";
import useSelectAll from "./hooks/use-handle-select-all";
import useSelectOptionsChange from "./hooks/use-select-options-change";
import useSelectedFlows from "./hooks/use-selected-flows";

export default function ComponentsComponent({
  type = "all",
}: {
  type?: string;
}) {
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const removeFlow = useFlowsManagerStore((state) => state.removeFlow);
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

  const [handleFileDrop] = useFileDrop(uploadFlow, type)!;
  const [pageSize, setPageSize] = useState(20);
  const [pageIndex, setPageIndex] = useState(1);
  const navigate = useNavigate();
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
  const addFlow = useFlowsManagerStore((state) => state.addFlow);

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
    getFolderById(folderId ? folderId : myCollectionId);
  }, [location]);

  useFilteredFlows(flowsFromFolder, searchFlowsComponents, setAllFlows);

  const resetFilter = () => {
    setPageIndex(1);
    setPageSize(20);
  };

  const { getValues, control, setValue } = useForm();
  const entireFormValues = useWatch({ control });

  const methods = useForm();

  const { handleSelectAll } = useSelectAll(
    flowsFromFolder,
    getValues,
    setValue,
  );

  const { handleDuplicate } = useDuplicateFlows(
    selectedFlowsComponentsCards,
    addFlow,
    allFlows,
    resetFilter,
    getFoldersApi,
    folderId,
    myCollectionId,
    getFolderById,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  );

  const version = useDarkStore((state) => state.version);

  const { handleExport } = useExportFlows(
    selectedFlowsComponentsCards,
    allFlows,
    downloadFlow,
    removeApiKeys,
    version,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  );

  const { handleSelectOptionsChange } = useSelectOptionsChange(
    selectedFlowsComponentsCards,
    setErrorData,
    setOpenDelete,
    handleDuplicate,
    handleExport,
  );

  const { handleDeleteMultiple } = useDeleteMultipleFlows(
    selectedFlowsComponentsCards,
    removeFlow,
    resetFilter,
    getFoldersApi,
    folderId,
    myCollectionId,
    getFolderById,
    setSuccessData,
    setErrorData,
  );

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
        <div className="flex h-full w-full flex-col justify-between">
          <div className="flex w-full flex-col gap-4">
            {!isLoading && data?.length === 0 ? (
              <EmptyComponent />
            ) : (
              <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-2">
                {isLoading === false && data?.length > 0 ? (
                  <>
                    {data?.map((item) => (
                      <FormProvider {...methods} key={item.id}>
                        <form>
                          <CollectionCardComponent
                            is_component={type === "component"}
                            data={{
                              is_component: item.is_component ?? false,
                              ...item,
                            }}
                            disabled={isLoading}
                            data-testid={"edit-flow-button-" + item.id}
                            button={
                              !item.is_component ? (
                                <Link to={"/flow/" + item.id}>
                                  <Button
                                    tabIndex={-1}
                                    variant="outline"
                                    size="sm"
                                    className="whitespace-nowrap"
                                    data-testid={"edit-flow-button-" + item.id}
                                  >
                                    <IconComponent
                                      name="ExternalLink"
                                      className="main-page-nav-button select-none"
                                    />
                                    Edit Flow
                                  </Button>
                                </Link>
                              ) : (
                                <></>
                              )
                            }
                            onClick={
                              !item.is_component
                                ? () => {
                                    navigate("/flow/" + item.id);
                                  }
                                : undefined
                            }
                            playground={!item.is_component}
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
