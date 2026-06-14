import type { ColDef } from "ag-grid-community";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import enTranslations from "@/locales/en.json";
import { formatFileSize } from "@/utils/stringManipulation";
import { FILE_ICONS } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import { getKnowledgeBaseBackendLabel } from "../utils/backendMetadata";
import {
  formatAverageChunkSize,
  formatNumber,
} from "../utils/knowledgeBaseUtils";
import { isBusyStatus, STATUS_CONFIG } from "./statusConfig";

export interface KnowledgeBaseColumnsCallbacks {
  onViewChunks?: (knowledgeBase: KnowledgeBaseInfo) => void;
  onDelete?: (knowledgeBase: KnowledgeBaseInfo) => void;
  onAddSources?: (knowledgeBase: KnowledgeBaseInfo) => void;
  onStopIngestion?: (knowledgeBase: KnowledgeBaseInfo) => void;
}

export const createKnowledgeBaseColumns = (
  callbacks?: KnowledgeBaseColumnsCallbacks,
  t: (key: string) => string = (key) =>
    enTranslations[key as keyof typeof enTranslations] ?? key,
): ColDef[] => {
  const baseCellClass =
    "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";

  const secondaryCellClass = `text-primary group-[.no-select-cells]:cursor-pointer group-[.no-select-cells]:select-none`;

  return [
    {
      headerName: t("knowledge.column.name"),
      field: "name",
      flex: 2,
      sortable: true,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: false,
      cellClass: secondaryCellClass,
      cellStyle: { textTransform: "none" },
      cellRenderer: (params: { data: KnowledgeBaseInfo; value: string }) => {
        const sourceTypes = params.data.source_types ?? [];
        const status = params.data.status ?? "empty";

        let iconName = "File";
        let iconColor: string | undefined = "text-muted-foreground";

        if (status === "empty" || sourceTypes.length === 0) {
          iconName = "File";
          iconColor = "text-muted-foreground";
        } else if (sourceTypes.length === 1) {
          const type = sourceTypes[0] as keyof typeof FILE_ICONS;
          iconName = FILE_ICONS[type]?.icon ?? "File";
          iconColor = FILE_ICONS[type]?.color ?? "text-accent-blue-foreground";
        } else {
          iconName = "Layers";
          iconColor = undefined;
        }

        return (
          <div className="flex items-center gap-3 pl-1">
            <div className="file-icon pointer-events-none relative">
              <ForwardedIconComponent
                name={iconName}
                className={cn("h-6 w-6 shrink-0", iconColor)}
              />
            </div>
            <span>{params.value}</span>
          </div>
        );
      },
    },
    {
      headerName: t("knowledge.column.size"),
      field: "size",
      flex: 1,
      sortable: false,
      valueFormatter: (params) => formatFileSize(params.value),
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: t("knowledge.column.embeddingModel"),
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
          Anthropic: "Anthropic",
          "Google Generative AI": "GoogleGenerativeAI",
          "IBM WatsonX": "WatsonxAI",
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
      headerName: t("knowledge.column.vectorStore"),
      field: "backend_type",
      flex: 1.3,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      cellRenderer: (params: { data: KnowledgeBaseInfo }) => (
        <span>
          {getKnowledgeBaseBackendLabel(
            params.data.backend_type,
            params.data.backend_config as Record<string, unknown> | undefined,
          )}
        </span>
      ),
    },
    {
      headerName: t("knowledge.column.chunks"),
      field: "chunks",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatNumber(params.value),
    },
    {
      headerName: t("knowledge.column.avgChunkSize"),
      field: "avg_chunk_size",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatAverageChunkSize(params.value),
    },
    {
      headerName: t("knowledge.column.status"),
      field: "status",
      flex: 1,
      sortable: false,
      editable: false,
      resizable: false,
      cellClass: baseCellClass,
      cellRenderer: (params: { data: KnowledgeBaseInfo }) => {
        const status = params.data?.status || "empty";
        const c = STATUS_CONFIG[status] || STATUS_CONFIG.empty;

        return (
          <div className="flex items-center h-full">
            <span className={cn("text-xs font-medium", c.textClass)}>
              {isBusyStatus(status) ? (
                <LoadingTextComponent text={t(c.label)} />
              ) : (
                t(c.label)
              )}
            </span>
          </div>
        );
      },
    },
    {
      headerName: "",
      field: "actions",
      width: 110,
      minWidth: 110,
      sortable: false,
      editable: false,
      resizable: false,
      suppressMovable: true,
      cellClass: "flex items-center justify-center text-primary",
      cellRenderer: (params: { data: KnowledgeBaseInfo }) => {
        const status = params.data?.status;
        const isBusy = isBusyStatus(status);
        const isCancelling = status === "cancelling";
        return (
          <div className="flex items-center justify-center gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={isBusy}
                    data-testid="kb-row-update-button"
                    aria-label={t("knowledge.action.ingestFiles")}
                    onClick={(e) => {
                      e.stopPropagation();
                      callbacks?.onAddSources?.(params.data);
                    }}
                  >
                    <ForwardedIconComponent
                      name="FileUp"
                      className="h-4 w-4 text-primary"
                    />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t("knowledge.action.ingestFiles")}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  data-testid="kb-row-actions-trigger"
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
                  disabled={isBusy}
                  onClick={(e) => {
                    e.stopPropagation();
                    callbacks?.onAddSources?.(params.data);
                  }}
                >
                  <ForwardedIconComponent
                    name="FileUp"
                    className="mr-2 h-4 w-4"
                  />
                  {t("knowledge.action.ingestFiles")}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    callbacks?.onViewChunks?.(params.data);
                  }}
                >
                  <ForwardedIconComponent
                    name="Layers"
                    className="mr-2 h-4 w-4"
                  />
                  {t("knowledge.action.viewChunks")}
                </DropdownMenuItem>
                {isBusy ? (
                  <DropdownMenuItem
                    disabled={isCancelling}
                    onClick={(e) => {
                      e.stopPropagation();
                      callbacks?.onStopIngestion?.(params.data);
                    }}
                    className="text-destructive focus:text-destructive"
                  >
                    <ForwardedIconComponent
                      name="Square"
                      className="mr-2 h-4 w-4"
                    />
                    {t("knowledge.action.stopIngestion")}
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      callbacks?.onDelete?.(params.data);
                    }}
                    className="text-destructive focus:text-destructive"
                  >
                    <ForwardedIconComponent
                      name="Trash2"
                      className="mr-2 h-4 w-4"
                    />
                    {t("knowledge.action.delete")}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
};
