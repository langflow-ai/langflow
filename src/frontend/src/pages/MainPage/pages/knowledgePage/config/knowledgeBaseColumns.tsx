import type { ColDef } from "ag-grid-community";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { formatFileSize } from "@/utils/stringManipulation";
import {
  formatAverageChunkSize,
  formatNumber,
} from "../utils/knowledgeBaseUtils";

export interface KnowledgeBaseColumnsCallbacks {
  onViewChunks?: (knowledgeBase: KnowledgeBaseInfo) => void;
  onDelete?: (knowledgeBase: KnowledgeBaseInfo) => void;
  onAddSources?: (knowledgeBase: KnowledgeBaseInfo) => void;
}

export const createKnowledgeBaseColumns = (
  callbacks?: KnowledgeBaseColumnsCallbacks,
): ColDef[] => {
  const baseCellClass =
    "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";

  const secondaryCellClass = `text-primary group-[.no-select-cells]:cursor-pointer group-[.no-select-cells]:select-none`;

  return [
    {
      headerName: "Name",
      field: "name",
      flex: 2,
      sortable: true,
      headerCheckboxSelection: true,
      checkboxSelection: false,
      editable: false,
      cellClass: secondaryCellClass,
      cellStyle: { textTransform: "none" },
    },
    {
      headerName: "Size",
      field: "size",
      flex: 1,
      sortable: false,
      valueFormatter: (params) => formatFileSize(params.value),
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Embedding Model",
      field: "embedding_model",
      flex: 1.5,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      cellRenderer: (params: { data: KnowledgeBaseInfo }) => {
        const model = params.data.embedding_model || "Unknown";
        const provider = params.data.embedding_provider || "Unknown";

        const providerIconMap: Record<string, string> = {
          OpenAI: "OpenAI",
          HuggingFace: "HuggingFace",
          Cohere: "Cohere",
          Google: "Google",
          Chroma: "Chroma",
          Mistral: "Mistral",
          Ollama: "Ollama",
          NVIDIA: "NVIDIA",
        };

        const iconName = providerIconMap[provider] || "Cpu";

        return (
          <div className="flex items-center gap-2">
            <ForwardedIconComponent
              name={iconName}
              className="h-4 w-4 shrink-0"
            />
            <span className="truncate">{model}</span>
          </div>
        );
      },
    },
    {
      headerName: "Chunks",
      field: "chunks",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatNumber(params.value),
    },
    {
      headerName: "Avg Chunk Size",
      field: "avg_chunk_size",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatAverageChunkSize(params.value),
    },
    {
      headerName: "Status",
      field: "status",
      flex: 1,
      sortable: false,
      editable: false,
      resizable: false,
      cellClass: baseCellClass,
      valueGetter: (params) => params.data.status || "—",
    },
    {
      headerName: "",
      field: "actions",
      width: 65,
      minWidth: 65,
      sortable: false,
      editable: false,
      resizable: false,
      suppressMovable: true,
      cellClass: "flex items-center justify-center text-primary",
      cellRenderer: (params: { data: KnowledgeBaseInfo }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => e.stopPropagation()}
            >
              <ForwardedIconComponent
                name="EllipsisVertical"
                className="h-4 w-4 text-primary"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                callbacks?.onAddSources?.(params.data);
              }}
            >
              <ForwardedIconComponent
                name="RefreshCw"
                className="mr-2 h-4 w-4"
              />
              Update Knowledge
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                callbacks?.onViewChunks?.(params.data);
              }}
            >
              <ForwardedIconComponent name="Layers" className="mr-2 h-4 w-4" />
              View Chunks
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                callbacks?.onDelete?.(params.data);
              }}
              className="text-destructive focus:text-destructive"
            >
              <ForwardedIconComponent name="Trash2" className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];
};
