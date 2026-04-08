import type { SelectionChangedEvent } from "ag-grid-community";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import {
  type FlowFileInfo,
  useGetFlowFiles,
} from "@/controllers/API/queries/file-management/use-get-flow-files";
import ConfirmationModal from "@/modals/confirmationModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { getFlowFilesColDefs } from "./flow-files-col-defs";
import { useFlowFileActions } from "./hooks/use-flow-file-actions";

const FlowFilesTab = () => {
  const { data: flowFiles, isLoading, isError } = useGetFlowFiles();
  const { handleDownload, handleDeleteSingle, handleBulkDelete } =
    useFlowFileActions();

  const [quickFilterText, setQuickFilterText] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<FlowFileInfo[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [fileToDelete, setFileToDelete] = useState<FlowFileInfo | null>(null);
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);

  const resetSelection = () => {
    setSelectedFiles([]);
    setQuantitySelected(0);
  };

  const closeDeleteModal = () => {
    setShowDeleteConfirmation(false);
    setFileToDelete(null);
  };

  const confirmDeleteSingle = () => {
    if (!fileToDelete) return;
    handleDeleteSingle(fileToDelete, closeDeleteModal);
  };

  const confirmBulkDelete = () => {
    handleBulkDelete(selectedFiles, { onComplete: resetSelection });
  };

  const handleSelectionChanged = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedFiles(selectedRows);
    setQuantitySelected(selectedRows.length);
  };

  const colDefs = getFlowFilesColDefs({
    onDownload: handleDownload,
    onDelete: (file) => {
      setFileToDelete(file);
      setShowDeleteConfirmation(true);
    },
  });

  return (
    <div className="flex h-full flex-col">
      {flowFiles && flowFiles.length > 0 && (
        <div className="flex justify-between">
          <div className="flex w-full xl:w-5/12">
            <Input
              icon="Search"
              data-testid="search-flow-files-input"
              type="text"
              placeholder="Search flow files..."
              className="mr-2 w-full"
              value={quickFilterText}
              onChange={(event) => setQuickFilterText(event.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            {quantitySelected > 0 && (
              <DeleteConfirmationModal
                onConfirm={confirmBulkDelete}
                description={"file" + (quantitySelected > 1 ? "s" : "")}
              >
                <Button
                  variant="destructive"
                  className="flex items-center gap-2 !px-3 font-semibold md:!px-4 md:!pl-3.5"
                  data-testid="bulk-delete-flow-files-btn"
                >
                  <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
                  <span className="hidden whitespace-nowrap md:inline">
                    Delete ({quantitySelected})
                  </span>
                </Button>
              </DeleteConfirmationModal>
            )}
          </div>
        </div>
      )}

      <div className="flex h-full flex-col py-4">
        {isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        ) : isError ? (
          <CardsWrapComponent dragMessage="">
            <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
              <div className="flex flex-col items-center gap-2">
                <h3 className="text-2xl font-semibold">
                  Error loading flow files
                </h3>
                <p className="text-lg text-secondary-foreground">
                  An error occurred while fetching your flow files. Please try
                  again later.
                </p>
              </div>
            </div>
          </CardsWrapComponent>
        ) : flowFiles && flowFiles.length > 0 ? (
          <div className="relative h-full">
            <TableComponent
              rowHeight={45}
              headerHeight={45}
              cellSelection={false}
              tableOptions={{ hide_options: true }}
              rowSelection="multiple"
              onSelectionChanged={handleSelectionChanged}
              columnDefs={colDefs}
              rowData={flowFiles}
              className="ag-no-border w-full"
              domLayout="autoHeight"
              pagination
              quickFilterText={quickFilterText}
              gridOptions={{
                ensureDomOrder: true,
                colResizeDefault: "shift",
              }}
            />
          </div>
        ) : (
          <CardsWrapComponent dragMessage="">
            <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
              <div className="flex flex-col items-center gap-2">
                <h3 className="text-2xl font-semibold">No flow files</h3>
                <p className="text-lg text-secondary-foreground">
                  Files uploaded to your flows will appear here.
                </p>
              </div>
            </div>
          </CardsWrapComponent>
        )}
      </div>

      <ConfirmationModal
        open={showDeleteConfirmation}
        onClose={closeDeleteModal}
        onCancel={closeDeleteModal}
        title="Delete File"
        titleHeader={`Are you sure you want to delete "${fileToDelete?.file_name}"?`}
        cancelText="Cancel"
        size="x-small"
        confirmationText="Delete"
        icon="Trash2"
        destructive
        onConfirm={confirmDeleteSingle}
      >
        <ConfirmationModal.Content>
          <div className="text-sm text-muted-foreground">
            This action cannot be undone. The file will be permanently deleted.
          </div>
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </div>
  );
};

export default FlowFilesTab;
