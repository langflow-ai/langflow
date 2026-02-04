import type { CellEditingStoppedEvent, ColDef } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import Loading from "@/components/ui/loading";
import {
  useGetDataset,
  type DatasetItemInfo,
} from "@/controllers/API/queries/datasets/use-get-dataset";
import { useCreateDatasetItem } from "@/controllers/API/queries/datasets/use-create-dataset-item";
import { useUpdateDatasetItem } from "@/controllers/API/queries/datasets/use-update-dataset-item";
import { useDeleteDatasetItem } from "@/controllers/API/queries/datasets/use-delete-dataset-item";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import ImportCsvModal from "@/modals/importCsvModal";
import useAlertStore from "@/stores/alertStore";
import { getURL } from "@/controllers/API/helpers/constants";

export const DatasetDetailPage = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const navigate = useCustomNavigate();
  const tableRef = useRef<AgGridReact<any>>(null);

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<DatasetItemInfo | null>(
    null,
  );

  const {
    data: dataset,
    isLoading,
    error,
    refetch,
  } = useGetDataset({ datasetId: datasetId || "" });

  const createItemMutation = useCreateDatasetItem({
    onSuccess: () => {
      setSuccessData({ title: "Item added successfully" });
      refetch();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to add item",
        list: [error?.message || "An unknown error occurred"],
      });
    },
  });

  const updateItemMutation = useUpdateDatasetItem({
    onSuccess: () => {
      setSuccessData({ title: "Item updated successfully" });
      refetch();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to update item",
        list: [error?.message || "An unknown error occurred"],
      });
    },
  });

  const handleDeleteItem = (item: DatasetItemInfo) => {
    setItemToDelete(item);
    setIsDeleteModalOpen(true);
  };

  const deleteItemMutation = useDeleteDatasetItem(
    {
      datasetId: datasetId || "",
      itemId: itemToDelete?.id || "",
    },
    {
      onSuccess: () => {
        setSuccessData({ title: "Item deleted successfully" });
        setItemToDelete(null);
        setIsDeleteModalOpen(false);
        refetch();
      },
      onError: (error: any) => {
        setErrorData({
          title: "Failed to delete item",
          list: [error?.message || "An unknown error occurred"],
        });
        setItemToDelete(null);
        setIsDeleteModalOpen(false);
      },
    },
  );

  const handleAddItem = () => {
    if (datasetId) {
      createItemMutation.mutate({
        datasetId,
        input: "",
        expected_output: "",
      });
    }
  };

  const handleCellEditingStopped = (event: CellEditingStoppedEvent) => {
    const { data, colDef, newValue, oldValue } = event;
    if (newValue !== oldValue && colDef.field && datasetId) {
      updateItemMutation.mutate({
        datasetId,
        itemId: data.id,
        [colDef.field]: newValue,
      });
    }
  };

  const handleExport = () => {
    if (datasetId) {
      window.open(`${getURL("DATASETS")}/${datasetId}/export/csv`, "_blank");
    }
  };

  const handleBack = () => {
    navigate("/assets/datasets");
  };

  const columnDefs: ColDef[] = [
    {
      headerName: "#",
      field: "order",
      width: 70,
      sortable: false,
      editable: false,
      cellClass: "text-muted-foreground",
      valueGetter: (params: any) => (params.node?.rowIndex ?? 0) + 1,
    },
    {
      headerName: "Input",
      field: "input",
      flex: 2,
      sortable: false,
      editable: true,
      cellClass: "cursor-text",
      cellEditor: "agLargeTextCellEditor",
      cellEditorPopup: true,
      cellEditorParams: {
        maxLength: 10000,
        rows: 10,
        cols: 50,
      },
    },
    {
      headerName: "Expected Output",
      field: "expected_output",
      flex: 2,
      sortable: false,
      editable: true,
      cellClass: "cursor-text",
      cellEditor: "agLargeTextCellEditor",
      cellEditorPopup: true,
      cellEditorParams: {
        maxLength: 10000,
        rows: 10,
        cols: 50,
      },
    },
    {
      headerName: "",
      field: "actions",
      width: 60,
      sortable: false,
      editable: false,
      cellRenderer: (params: any) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={(e) => {
            e.stopPropagation();
            handleDeleteItem(params.data);
          }}
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
        >
          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  if (error) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">Failed to load dataset</p>
          <Button variant="outline" onClick={handleBack} className="mt-4">
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading || !dataset) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full" data-testid="dataset-detail-wrapper">
      <div className="flex h-full w-full flex-col overflow-y-auto transition-all duration-200">
        <div className="flex h-full w-full flex-col xl:container">
          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
            <div className="flex h-full flex-col justify-start">
              {/* Header */}
              <div className="flex items-center justify-between pb-8">
                <div className="flex items-center gap-4">
                  <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                    <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                      <SidebarTrigger>
                        <ForwardedIconComponent
                          name="PanelLeftOpen"
                          aria-hidden="true"
                        />
                      </SidebarTrigger>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleBack}
                    className="mr-2"
                  >
                    <ForwardedIconComponent name="ArrowLeft" className="h-5 w-5" />
                  </Button>
                  <div className="flex items-center gap-2">
                    <ForwardedIconComponent
                      name="Database"
                      className="h-5 w-5 text-muted-foreground"
                    />
                    <h1 className="text-xl font-semibold">{dataset.name}</h1>
                    {dataset.description && (
                      <span className="text-sm text-muted-foreground">
                        - {dataset.description}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setIsImportModalOpen(true)}
                    className="flex items-center gap-2"
                  >
                    <ForwardedIconComponent name="Upload" className="h-4 w-4" />
                    Import CSV
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleExport}
                    className="flex items-center gap-2"
                  >
                    <ForwardedIconComponent name="Download" className="h-4 w-4" />
                    Export
                  </Button>
                  <Button
                    onClick={handleAddItem}
                    className="flex items-center gap-2"
                    disabled={createItemMutation.isPending}
                  >
                    <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                    Add Item
                  </Button>
                </div>
              </div>

              {/* Table */}
              <div className="flex h-full flex-col pb-4">
                <div className="relative h-full">
                  {dataset.items.length === 0 ? (
                    <div className="flex h-full flex-col items-center justify-center gap-4 py-20">
                      <ForwardedIconComponent
                        name="Database"
                        className="h-12 w-12 text-muted-foreground"
                      />
                      <p className="text-lg text-muted-foreground">
                        No items in this dataset yet
                      </p>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          onClick={() => setIsImportModalOpen(true)}
                        >
                          <ForwardedIconComponent
                            name="Upload"
                            className="mr-2 h-4 w-4"
                          />
                          Import CSV
                        </Button>
                        <Button onClick={handleAddItem}>
                          <ForwardedIconComponent
                            name="Plus"
                            className="mr-2 h-4 w-4"
                          />
                          Add Item
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <TableComponent
                      rowHeight={60}
                      headerHeight={45}
                      cellSelection={false}
                      tableOptions={{
                        hide_options: true,
                      }}
                      columnDefs={columnDefs}
                      rowData={dataset.items}
                      className="ag-no-border ag-dataset-detail-table w-full"
                      pagination
                      ref={tableRef}
                      onCellEditingStopped={handleCellEditingStopped}
                      gridOptions={{
                        stopEditingWhenCellsLoseFocus: true,
                        ensureDomOrder: true,
                        colResizeDefault: "shift",
                        singleClickEdit: false,
                      }}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ImportCsvModal
        open={isImportModalOpen}
        setOpen={setIsImportModalOpen}
        datasetId={datasetId || ""}
        onSuccess={() => {
          refetch();
        }}
      />

      <DeleteConfirmationModal
        open={isDeleteModalOpen}
        setOpen={setIsDeleteModalOpen}
        onConfirm={() => {
          if (!deleteItemMutation.isPending) {
            deleteItemMutation.mutate();
          }
        }}
        description="this item"
        note="This action cannot be undone."
      >
        <></>
      </DeleteConfirmationModal>
    </div>
  );
};

export default DatasetDetailPage;
