import type { RowClickedEvent, SelectionChangedEvent } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { useDeleteKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-delete-knowledge-base";
import {
  type KnowledgeBaseInfo,
  useGetKnowledgeBases,
} from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { createKnowledgeBaseColumns } from "../config/knowledgeBaseColumns";
import KnowledgeBaseEmptyState from "./KnowledgeBaseEmptyState";
import KnowledgeBaseSelectionOverlay from "./KnowledgeBaseSelectionOverlay";

interface KnowledgeBasesTabProps {
  quickFilterText: string;
  setQuickFilterText: (text: string) => void;
  selectedFiles: any[];
  setSelectedFiles: (files: any[]) => void;
  quantitySelected: number;
  setQuantitySelected: (quantity: number) => void;
  isShiftPressed: boolean;
  onRowClick?: (knowledgeBase: KnowledgeBaseInfo) => void;
}

const KnowledgeBasesTab = ({
  quickFilterText,
  setQuickFilterText,
  selectedFiles,
  setSelectedFiles,
  quantitySelected,
  setQuantitySelected,
  isShiftPressed,
  onRowClick,
}: KnowledgeBasesTabProps) => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const examples = useFlowsManagerStore((state) => state.examples);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folderIdUrl = folderId ?? myCollectionId;

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [knowledgeBaseToDelete, setKnowledgeBaseToDelete] =
    useState<KnowledgeBaseInfo | null>(null);

  const { data: knowledgeBases, isLoading, error } = useGetKnowledgeBases();

  const deleteKnowledgeBaseMutation = useDeleteKnowledgeBase(
    {
      kb_name: knowledgeBaseToDelete?.id || "",
    },
    {
      onSuccess: () => {
        setSuccessData({
          title: `Knowledge Base "${knowledgeBaseToDelete?.name}" deleted successfully!`,
        });
        resetDeleteState();
      },
      onError: (error: any) => {
        setErrorData({
          title: "Failed to delete knowledge base",
          list: [
            error?.response?.data?.detail ||
              error?.message ||
              "An unknown error occurred",
          ],
        });
        resetDeleteState();
      },
    },
  );

  if (error) {
    setErrorData({
      title: "Failed to load knowledge bases",
      list: [error?.message || "An unknown error occurred"],
    });
  }

  const resetDeleteState = () => {
    setKnowledgeBaseToDelete(null);
    setIsDeleteModalOpen(false);
  };

  const handleDelete = (knowledgeBase: KnowledgeBaseInfo) => {
    setKnowledgeBaseToDelete(knowledgeBase);
    setIsDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (knowledgeBaseToDelete && !deleteKnowledgeBaseMutation.isPending) {
      deleteKnowledgeBaseMutation.mutate();
    }
  };

  const handleSelectionChange = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedFiles(selectedRows);
    if (selectedRows.length > 0) {
      setQuantitySelected(selectedRows.length);
    } else {
      setTimeout(() => {
        setQuantitySelected(0);
      }, 300);
    }
  };

  const handleCreateKnowledge = async () => {
    const knowledgeBasesExample = examples.find(
      (example) => example.name === "Knowledge Ingestion",
    );

    if (knowledgeBasesExample && knowledgeBasesExample.data) {
      updateIds(knowledgeBasesExample.data);
      addFlow({ flow: knowledgeBasesExample }).then((id) => {
        navigate(`/flow/${id}/folder/${folderIdUrl}`);
      });
      track("New Flow Created", {
        template: `${knowledgeBasesExample.name} Template`,
      });
    }
  };

  const clearSelection = () => {
    setQuantitySelected(0);
    setSelectedFiles([]);
  };

  const handleRowClick = (event: RowClickedEvent) => {
    const clickedElement = event.event?.target as HTMLElement;
    if (clickedElement && !clickedElement.closest("button") && onRowClick) {
      onRowClick(event.data);
    }
  };

  const columnDefs = createKnowledgeBaseColumns();

  if (isLoading || !knowledgeBases || !Array.isArray(knowledgeBases)) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (knowledgeBases.length === 0) {
    return (
      <KnowledgeBaseEmptyState handleCreateKnowledge={handleCreateKnowledge} />
    );
  }

  return (
    <div className="flex h-full flex-col pb-4">
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="Search"
            data-testid="search-kb-input"
            type="text"
            placeholder="Search knowledge bases..."
            className="mr-2 w-full"
            value={quickFilterText || ""}
            onChange={(event) => setQuickFilterText(event.target.value)}
          />
        </div>
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={handleCreateKnowledge}
        >
          <ForwardedIconComponent name="Plus" /> Create knowledge
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
            rowData={knowledgeBases}
            className={cn(
              "ag-no-border ag-knowledge-table group w-full",
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

          <KnowledgeBaseSelectionOverlay
            selectedFiles={selectedFiles}
            quantitySelected={quantitySelected}
            onClearSelection={clearSelection}
          />
        </div>
      </div>

      <DeleteConfirmationModal
        open={isDeleteModalOpen}
        setOpen={setIsDeleteModalOpen}
        onConfirm={confirmDelete}
        description={`knowledge base "${knowledgeBaseToDelete?.name || ""}"`}
        note="This action cannot be undone"
      >
        <></>
      </DeleteConfirmationModal>
    </div>
  );
};

export default KnowledgeBasesTab;
