import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useRef } from "react";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { useGetKnowledgeBases } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { createKnowledgeBaseColumns } from "../config/knowledgeBaseColumns";
import CreateKnowledgeBaseButton from "./CreateKnowledgeBaseButton";
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
}

const KnowledgeBasesTab = ({
  quickFilterText,
  setQuickFilterText,
  selectedFiles,
  setSelectedFiles,
  quantitySelected,
  setQuantitySelected,
  isShiftPressed,
}: KnowledgeBasesTabProps) => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  // Fetch knowledge bases from API
  const { data: knowledgeBases, isLoading, error } = useGetKnowledgeBases();

  // Handle errors
  if (error) {
    setErrorData({
      title: "Failed to load knowledge bases",
      list: [error?.message || "An unknown error occurred"],
    });
  }

  const handleRename = (params: NewValueParams<any, any>) => {
    // TODO: Implement knowledge base rename functionality
    setSuccessData({
      title: "Knowledge Base renamed successfully!",
    });
  };

  const handleSelectionChanged = (event: SelectionChangedEvent) => {
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

  const handleClearSelection = () => {
    setQuantitySelected(0);
    setSelectedFiles([]);
  };

  // Get column definitions
  const columnDefs = createKnowledgeBaseColumns(handleRename);

  // Show loading state
  if (isLoading || !knowledgeBases || !Array.isArray(knowledgeBases)) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading />
      </div>
    );
  }

  // Show empty state
  if (knowledgeBases.length === 0) {
    return <KnowledgeBaseEmptyState />;
  }

  // Show table with data
  return (
    <div className="flex h-full flex-col pb-4">
      {/* Search and Create Button */}
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="Search"
            data-testid="search-kb-input"
            type="text"
            placeholder="Search knowledge bases..."
            className="mr-2 w-full"
            value={quickFilterText || ""}
            onChange={(event) => {
              setQuickFilterText(event.target.value);
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <CreateKnowledgeBaseButton />
        </div>
      </div>

      {/* Table */}
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
            editable={[
              {
                field: "name",
                onUpdate: handleRename,
                editableCell: true,
              },
            ]}
            rowSelection="multiple"
            onSelectionChanged={handleSelectionChanged}
            columnDefs={columnDefs}
            rowData={knowledgeBases}
            className={cn(
              "ag-no-border group w-full",
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

          {/* Selection Overlay */}
          <KnowledgeBaseSelectionOverlay
            selectedFiles={selectedFiles}
            quantitySelected={quantitySelected}
            onClearSelection={handleClearSelection}
          />
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBasesTab;
