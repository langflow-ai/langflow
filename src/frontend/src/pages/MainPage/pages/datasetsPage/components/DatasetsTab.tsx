import type {
  RowClickedEvent,
  SelectionChangedEvent,
} from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import {
  type DatasetInfo,
  useGetDatasets,
} from "@/controllers/API/queries/datasets/use-get-datasets";
import { useDeleteDatasets } from "@/controllers/API/queries/datasets/use-delete-datasets";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import DatasetEmptyState from "./DatasetEmptyState";
import DatasetSelectionOverlay from "./DatasetSelectionOverlay";
import { createDatasetColumns } from "../config/datasetColumns";

interface DatasetsTabProps {
  quickFilterText: string;
  setQuickFilterText: (text: string) => void;
  selectedDatasets: DatasetInfo[];
  setSelectedDatasets: (datasets: DatasetInfo[]) => void;
  quantitySelected: number;
  setQuantitySelected: (quantity: number) => void;
  isShiftPressed: boolean;
  onCreateDataset: () => void;
}

const DatasetsTab = ({
  quickFilterText,
  setQuickFilterText,
  selectedDatasets,
  setSelectedDatasets,
  quantitySelected,
  setQuantitySelected,
  isShiftPressed,
  onCreateDataset,
}: DatasetsTabProps) => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const navigate = useCustomNavigate();

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [datasetsToDelete, setDatasetsToDelete] = useState<DatasetInfo[]>([]);

  const { data: datasets, isLoading, error } = useGetDatasets();

  const deleteDatasetsMutation = useDeleteDatasets({
    onSuccess: (data) => {
      setSuccessData({
        title: `${data.deleted} dataset(s) deleted successfully!`,
      });
      resetDeleteState();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to delete datasets",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
      resetDeleteState();
    },
  });

  if (error) {
    setErrorData({
      title: "Failed to load datasets",
      list: [error?.message || "An unknown error occurred"],
    });
  }

  const resetDeleteState = () => {
    setDatasetsToDelete([]);
    setIsDeleteModalOpen(false);
    setSelectedDatasets([]);
    setQuantitySelected(0);
  };

  const handleDeleteSelected = () => {
    if (selectedDatasets.length > 0) {
      setDatasetsToDelete(selectedDatasets);
      setIsDeleteModalOpen(true);
    }
  };

  const confirmDelete = () => {
    if (datasetsToDelete.length > 0 && !deleteDatasetsMutation.isPending) {
      deleteDatasetsMutation.mutate({
        dataset_ids: datasetsToDelete.map((d) => d.id),
      });
    }
  };

  const handleSelectionChange = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedDatasets(selectedRows);
    if (selectedRows.length > 0) {
      setQuantitySelected(selectedRows.length);
    } else {
      setTimeout(() => {
        setQuantitySelected(0);
      }, 300);
    }
  };

  const clearSelection = () => {
    setQuantitySelected(0);
    setSelectedDatasets([]);
    tableRef.current?.api?.deselectAll();
  };

  const handleRowClick = (event: RowClickedEvent) => {
    const clickedElement = event.event?.target as HTMLElement;
    if (clickedElement && !clickedElement.closest("button")) {
      navigate(`/assets/datasets/${event.data.id}`);
    }
  };

  const columnDefs = createDatasetColumns();

  if (isLoading || !datasets || !Array.isArray(datasets)) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (datasets.length === 0) {
    return <DatasetEmptyState onCreateDataset={onCreateDataset} />;
  }

  return (
    <div className="flex h-full flex-col pb-4">
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="Search"
            data-testid="search-dataset-input"
            type="text"
            placeholder="Search datasets..."
            className="mr-2 w-full"
            value={quickFilterText || ""}
            onChange={(event) => setQuickFilterText(event.target.value)}
          />
        </div>
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={onCreateDataset}
        >
          <ForwardedIconComponent name="Plus" /> New Dataset
        </Button>
      </div>

      <div className="flex h-full flex-col pt-4">
        <div className="relative h-full">
          <TableComponent
            rowHeight={45}
            headerHeight={45}
            cellSelection={false}
            tableOptions={{
              hide_options: true,
            }}
            suppressRowClickSelection={!isShiftPressed}
            rowSelection="multiple"
            onSelectionChanged={handleSelectionChange}
            onRowClicked={handleRowClick}
            columnDefs={columnDefs}
            rowData={datasets}
            className={cn(
              "ag-no-border ag-dataset-table group w-full",
              isShiftPressed && quantitySelected > 0 && "no-select-cells",
            )}
            pagination
            ref={tableRef}
            quickFilterText={quickFilterText}
            gridOptions={{
              stopEditingWhenCellsLoseFocus: true,
              ensureDomOrder: true,
              colResizeDefault: "shift",
            }}
          />

          <DatasetSelectionOverlay
            selectedDatasets={selectedDatasets}
            quantitySelected={quantitySelected}
            onClearSelection={clearSelection}
            onDeleteSelected={handleDeleteSelected}
          />
        </div>
      </div>

      <DeleteConfirmationModal
        open={isDeleteModalOpen}
        setOpen={setIsDeleteModalOpen}
        onConfirm={confirmDelete}
        description={`${datasetsToDelete.length} dataset(s)`}
        note="This action cannot be undone. All items in the dataset(s) will also be deleted."
      >
        <></>
      </DeleteConfirmationModal>
    </div>
  );
};

export default DatasetsTab;
