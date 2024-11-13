import { PAGINATION_PAGE, PAGINATION_SIZE } from "@/constants/constants";
import { usePostDownloadMultipleFlows } from "@/controllers/API/queries/flows";
import TemplatesModal from "@/modals/templatesModal";
import { Pagination } from "@/types/utils/types";
import { useEffect, useMemo, useState } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";
import { useLocation, useParams } from "react-router-dom";
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
  currentFolder,
  pagination,
  isLoading,
  deleteFlow,
  onPaginate,
}: {
  type?: string;
  currentFolder?: FlowType[];
  isLoading: boolean;
  pagination: Pagination;
  deleteFlow: ({ id }: { id: string[] }) => Promise<void>;
  onPaginate: (pageIndex: number, pageSize: number) => void;
}) {
  const { folderId } = useParams();

  const [openModal, setOpenModal] = useState(false);

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
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const flowsFromFolder = currentFolder ?? [];

  const [filteredFlows, setFilteredFlows] =
    useState<FlowType[]>(flowsFromFolder);

  const handleFileDrop = useFileDrop(type);
  const location = useLocation();

  const name = getNameByType(type);

  const [shouldSelectAll, setShouldSelectAll] = useState(true);

  const cardTypes = useMemo(() => {
    if (location.pathname.includes("components")) {
      return "Components";
    }
    if (location.pathname.includes("flows")) {
      return "Flows";
    }
    return "Items";
  }, [location]);

  useEffect(() => {
    setSelectedFlowsComponentsCards([]);
    handleSelectAll(false);
    setShouldSelectAll(true);
  }, [folderId, location, myCollectionId]);

  useFilteredFlows(flowsFromFolder, searchFlowsComponents, setFilteredFlows);

  const resetFilter = () => {
    onPaginate(PAGINATION_PAGE, PAGINATION_SIZE);
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
    flowsFromFolder,
    resetFilter,
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
          const selectedFlow = flowsFromFolder.find(
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

  const handleDeleteMultiple = () => {
    deleteFlow({ id: selectedFlowsComponentsCards })
      .then(() => {
        resetFilter();
        setSelectedFlowsComponentsCards([]);
        handleSelectAll(false);
        setShouldSelectAll(true);
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch(() => {
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

  const handleOpenModal = () => {
    setOpenModal(true);
  };

  return (
    <>
      <div className="flex w-full gap-4 pb-5">
        <HeaderComponent
          disabled={isLoading || flowsFromFolder?.length === 0}
          shouldSelectAll={shouldSelectAll}
          setShouldSelectAll={setShouldSelectAll}
          handleDelete={() => handleSelectOptionsChange("delete")}
          handleSelectAll={handleSelectAll}
          handleDuplicate={() => handleSelectOptionsChange("duplicate")}
          handleExport={() => handleSelectOptionsChange("export")}
          disableFunctions={!(selectedFlowsComponentsCards?.length > 0)}
        />
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
            {!isLoading && flowsFromFolder?.length === 0 ? (
              <EmptyComponent handleOpenModal={handleOpenModal} />
            ) : (
              <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-2">
                {flowsFromFolder?.length > 0 ? (
                  <>
                    {flowsFromFolder?.map((item) => (
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
          {!isLoading && flowsFromFolder?.length > 0 && (
            <div className="relative py-6">
              <PaginatorComponent
                pageIndex={pagination.page}
                pageSize={pagination.size}
                rowsCount={[10, 20, 50, 100]}
                totalRowsCount={pagination.total ?? 0}
                paginate={onPaginate}
                pages={pagination.pages}
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
      <TemplatesModal open={openModal} setOpen={setOpenModal} />
    </>
  );
}
