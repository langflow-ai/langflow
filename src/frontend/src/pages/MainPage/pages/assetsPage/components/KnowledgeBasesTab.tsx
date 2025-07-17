import type {
  ColDef,
  NewValueParams,
  SelectionChangedEvent,
} from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { useGetKnowledgeBases } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { formatFileSize } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";

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

  const CreateKnowledgeBaseButtonComponent = useMemo(() => {
    return (
      <ShadTooltip content="Create Knowledge Base" side="bottom">
        <Button
          className="!px-3 md:!px-4 md:!pl-3.5"
          onClick={() => {
            // TODO: Implement create knowledge base functionality
            setSuccessData({
              title: "Knowledge Base creation coming soon!",
            });
          }}
          id="create-kb-btn"
          data-testid="create-kb-btn"
        >
          <ForwardedIconComponent
            name="Plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="hidden whitespace-nowrap font-semibold md:inline">
            Create KB
          </span>
        </Button>
      </ShadTooltip>
    );
  }, [setSuccessData]);

  // Helper function to format numbers with commas
  const formatNumber = (num: number) => {
    return new Intl.NumberFormat().format(num);
  };

  // Column definitions for Knowledge Bases
  const knowledgeBaseColDefs: ColDef[] = [
    {
      headerName: "Name",
      field: "name",
      flex: 2,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: true,
      filter: "agTextColumnFilter",
      cellClass:
        "cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      cellRenderer: (params) => {
        return (
          <div className="flex items-center gap-3 font-medium">
            <div className="flex flex-col">
              <div className="text-sm font-medium">{params.value}</div>
            </div>
          </div>
        );
      },
    },
    {
      headerName: "Embedding Provider",
      field: "embedding_provider",
      flex: 1.2,
      filter: "agTextColumnFilter",
      editable: false,
      cellClass:
        "cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      cellRenderer: (params) => {
        return (
          <div className="flex items-center gap-2">
            <span className="text-sm">{params.value || "Unknown"}</span>
          </div>
        );
      },
    },
    {
      headerName: "Size",
      field: "size",
      flex: 0.8,
      valueFormatter: (params) => {
        return formatFileSize(params.value);
      },
      editable: false,
      cellClass:
        "text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
    },
    {
      headerName: "Words",
      field: "words",
      flex: 0.8,
      editable: false,
      cellClass:
        "text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      valueFormatter: (params) => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: "Characters",
      field: "characters",
      flex: 1,
      editable: false,
      cellClass:
        "text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      valueFormatter: (params) => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: "Chunks",
      field: "chunks",
      flex: 0.7,
      editable: false,
      cellClass:
        "text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      valueFormatter: (params) => {
        return formatNumber(params.value);
      },
    },
    {
      headerName: "Avg Chunks",
      field: "avg_chunk_size",
      flex: 1,
      editable: false,
      cellClass:
        "text-muted-foreground cursor-text select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none",
      valueFormatter: (params) => {
        return `${formatNumber(Math.round(params.value))} chars`;
      },
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: "cursor-default",
      cellRenderer: (params) => {
        return (
          <div className="flex h-full cursor-default items-center justify-center">
            <Button variant="ghost" size="iconMd">
              <ForwardedIconComponent name="EllipsisVertical" />
            </Button>
          </div>
        );
      },
    },
  ];

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

  return (
    <div className="flex h-full flex-col pb-4">
      {knowledgeBases && knowledgeBases.length !== 0 ? (
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
            {CreateKnowledgeBaseButtonComponent}
          </div>
        </div>
      ) : (
        <></>
      )}

      <div className="flex h-full flex-col pt-4">
        {isLoading || !knowledgeBases || !Array.isArray(knowledgeBases) ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        ) : knowledgeBases.length > 0 ? (
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
                  onUpdate: (params: NewValueParams<any, any>) => {
                    // TODO: Implement knowledge base rename functionality
                    setSuccessData({
                      title: "Knowledge Base renamed successfully!",
                    });
                  },
                  editableCell: true,
                },
              ]}
              rowSelection="multiple"
              onSelectionChanged={handleSelectionChanged}
              columnDefs={knowledgeBaseColDefs}
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

            <div
              className={cn(
                "pointer-events-none absolute top-1.5 z-50 flex h-8 w-full transition-opacity",
                selectedFiles.length > 0 ? "opacity-100" : "opacity-0",
              )}
            >
              <div
                className={cn(
                  "ml-12 flex h-full flex-1 items-center justify-between bg-background",
                  selectedFiles.length > 0
                    ? "pointer-events-auto"
                    : "pointer-events-none",
                )}
              >
                <span className="text-xs text-muted-foreground">
                  {quantitySelected} selected
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="iconMd"
                    onClick={() => {
                      // TODO: Implement knowledge base export functionality
                      setSuccessData({
                        title: "Knowledge Base export coming soon!",
                      });
                    }}
                    data-testid="bulk-export-kb-btn"
                  >
                    <ForwardedIconComponent name="Download" />
                  </Button>

                  <DeleteConfirmationModal
                    onConfirm={() => {
                      // TODO: Implement knowledge base delete functionality
                      setSuccessData({
                        title: "Knowledge Base(s) deleted successfully!",
                      });
                      setQuantitySelected(0);
                      setSelectedFiles([]);
                    }}
                    description={
                      "knowledge base" + (quantitySelected > 1 ? "s" : "")
                    }
                  >
                    <Button
                      variant="destructive"
                      size="iconMd"
                      className="px-2.5 !text-mmd"
                      data-testid="bulk-delete-kb-btn"
                    >
                      <ForwardedIconComponent name="Trash2" />
                      Delete
                    </Button>
                  </DeleteConfirmationModal>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
            <div className="flex flex-col items-center gap-2">
              <h3 className="text-2xl font-semibold">No knowledge bases</h3>
              <p className="text-lg text-secondary-foreground">
                Create your first knowledge base to get started.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {CreateKnowledgeBaseButtonComponent}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBasesTab;
