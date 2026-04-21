import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelInputComponent, {
  type ModelOption,
} from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useGetConnectors } from "@/controllers/API/queries/knowledge-bases/use-get-connectors";
import type { DeferredConnectorPayload } from "@/pages/MainPage/pages/knowledgePage/components/connectorPayload";
import GoogleDriveConnectorForm from "@/pages/MainPage/pages/knowledgePage/components/GoogleDriveConnectorForm";
import OneDriveConnectorForm from "@/pages/MainPage/pages/knowledgePage/components/OneDriveConnectorForm";
import S3ConnectorForm from "@/pages/MainPage/pages/knowledgePage/components/S3ConnectorForm";
import SharePointConnectorForm from "@/pages/MainPage/pages/knowledgePage/components/SharePointConnectorForm";
import { cn } from "@/utils/utils";
import { ACCEPTED_FILE_TYPES } from "../constants";
import type { ColumnConfigRow } from "../types";
import { BackendPicker, type BackendValue } from "./BackendPicker";

const SUPPORTED_CONNECTORS = ["s3", "google_drive", "onedrive", "sharepoint"];

interface StepConfigurationProps {
  isAddSourcesMode: boolean;
  sourceName: string;
  onSourceNameChange: (value: string) => void;
  selectedEmbeddingModel: ModelOption[];
  onEmbeddingModelChange: (value: ModelOption[]) => void;
  embeddingModelOptions: ModelOption[];
  existingEmbeddingModel?: string;
  existingEmbeddingIcon?: string;
  chunkSize: number;
  onChunkSizeChange: (value: number) => void;
  chunkOverlap: number;
  onChunkOverlapChange: (value: number) => void;
  separator: string;
  onSeparatorChange: (value: string) => void;
  showAdvanced: boolean;
  toggleAdvanced: () => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFolderSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  validationErrors?: Record<string, string>;
  onFieldChange?: () => void;
  columnConfig: ColumnConfigRow[];
  onColumnConfigChange: (value: ColumnConfigRow[]) => void;
  backendType: string;
  onBackendTypeChange: (value: string) => void;
  backendConfig: Record<string, string>;
  onBackendConfigChange: (value: Record<string, string>) => void;
  activeConnector: string | null;
  onSelectConnector: (sourceType: string | null) => void;
  onConnectorPayloadChange: (payload: DeferredConnectorPayload | null) => void;
}

export function StepConfiguration({
  isAddSourcesMode,
  sourceName,
  onSourceNameChange,
  selectedEmbeddingModel,
  onEmbeddingModelChange,
  embeddingModelOptions,
  existingEmbeddingModel,
  existingEmbeddingIcon,
  chunkSize,
  onChunkSizeChange,
  chunkOverlap,
  onChunkOverlapChange,
  separator,
  onSeparatorChange,
  showAdvanced,
  toggleAdvanced,
  onFileSelect,
  onFolderSelect,
  validationErrors = {},
  onFieldChange,
  columnConfig,
  onColumnConfigChange,
  backendType,
  onBackendTypeChange,
  backendConfig,
  onBackendConfigChange,
  activeConnector,
  onSelectConnector,
  onConnectorPayloadChange,
}: StepConfigurationProps) {
  const { data: connectorsCatalog } = useGetConnectors(undefined);
  const supportedConnectors =
    connectorsCatalog?.filter((c) =>
      SUPPORTED_CONNECTORS.includes(c.source_type),
    ) ?? [];
  const activeConnectorEntry = connectorsCatalog?.find(
    (c) => c.source_type === activeConnector,
  );
  return (
    <div className="relative">
      <div className="flex flex-col">
        {/* Name */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="source-name" className="text-sm font-medium">
            Name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="source-name"
            placeholder="Enter a name for this knowledge base"
            value={sourceName}
            onChange={(e) => {
              onSourceNameChange(e.target.value);
              onFieldChange?.();
            }}
            data-testid="kb-source-name-input"
            disabled={isAddSourcesMode}
            className={validationErrors.sourceName ? "border-destructive" : ""}
          />
          {validationErrors.sourceName && (
            <span className="text-xs text-destructive">
              {validationErrors.sourceName}
            </span>
          )}
        </div>

        {/* Model Selection */}
        <div className="flex flex-col gap-2 pt-4">
          <Label className="text-sm font-medium">
            Embedding Model <span className="text-destructive">*</span>
          </Label>
          {isAddSourcesMode ? (
            <div className="flex h-10 w-full items-center gap-2 rounded-md border border-input bg-muted px-3 py-2 text-sm">
              <ForwardedIconComponent
                name={existingEmbeddingIcon || "Cpu"}
                className="h-4 w-4 shrink-0"
              />
              <span className="text-muted-foreground">
                {existingEmbeddingModel || "Unknown"}
              </span>
            </div>
          ) : (
            <div
              className={cn(
                "rounded-md",
                validationErrors.embeddingModel &&
                  "[&_button]:border-destructive",
              )}
            >
              <ModelInputComponent
                id="kb-embedding-model"
                value={selectedEmbeddingModel}
                editNode={false}
                disabled={false}
                handleOnNewValue={({ value }) => {
                  onEmbeddingModelChange(value);
                  onFieldChange?.();
                }}
                options={embeddingModelOptions}
                placeholder="Select embedding model"
                showEmptyState
              />
            </div>
          )}
          {validationErrors.embeddingModel && (
            <span className="text-xs text-destructive">
              {validationErrors.embeddingModel}
            </span>
          )}
        </div>

        {/* Vector Store Backend (Phase 4) — immutable once the KB
            is created, so we hide it in add-sources mode. */}
        {!isAddSourcesMode && (
          <div className="flex flex-col gap-2 pt-4">
            <BackendPicker
              value={backendType as BackendValue}
              onValueChange={(v) => {
                onBackendTypeChange(v);
                onFieldChange?.();
              }}
              config={backendConfig}
              onConfigChange={(c) => {
                onBackendConfigChange(c);
                onFieldChange?.();
              }}
            />
            {validationErrors.backend && (
              <span className="text-xs text-destructive">
                {validationErrors.backend}
              </span>
            )}
          </div>
        )}

        {/* Hidden file inputs */}
        <input
          id="file-input"
          type="file"
          multiple
          className="hidden"
          onChange={onFileSelect}
          accept={ACCEPTED_FILE_TYPES}
        />
        <input
          id="folder-input"
          type="file"
          multiple
          className="hidden"
          onChange={onFolderSelect}
          accept={ACCEPTED_FILE_TYPES}
          {...({
            webkitdirectory: "",
            directory: "",
          } as React.HTMLAttributes<HTMLInputElement>)}
        />

        {/* Configure Sources - Animated */}
        <div
          className={cn(
            "grid transition-all duration-300 ease-in-out",
            showAdvanced
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            <Separator className="my-4" />
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="LayoutGrid"
                  className="h-4 w-4 text-muted-foreground"
                />
                <span className="text-sm font-medium">
                  Configure Sources
                  <span className="text-xs text-muted-foreground ml-1">
                    (1 GB max upload)
                  </span>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label className="text-xs text-muted-foreground">
                    Sources
                  </Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        data-testid="kb-browse-btn"
                        className={cn(
                          "w-full justify-between focus-visible:ring-1 focus-visible:ring-offset-0 focus-visible:ring-offset-background ",
                          validationErrors.files && "border-destructive",
                        )}
                      >
                        <span className="flex items-center gap-2">
                          <ForwardedIconComponent
                            name="Upload"
                            className="h-4 w-4"
                          />
                          Add Sources
                        </span>
                        <ForwardedIconComponent
                          name="ChevronDown"
                          className="h-4 w-4"
                        />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-[220px]">
                      <DropdownMenuItem
                        onClick={() => {
                          onSelectConnector(null);
                          document.getElementById("file-input")?.click();
                        }}
                      >
                        <ForwardedIconComponent
                          name="FileText"
                          className="mr-2 h-4 w-4"
                        />
                        Upload Files
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          onSelectConnector(null);
                          document.getElementById("folder-input")?.click();
                        }}
                      >
                        <ForwardedIconComponent
                          name="Folder"
                          className="mr-2 h-4 w-4"
                        />
                        Upload Folder
                      </DropdownMenuItem>
                      {supportedConnectors.length > 0 && (
                        <DropdownMenuSeparator />
                      )}
                      {supportedConnectors.map((connector) => (
                        <DropdownMenuItem
                          key={connector.source_type}
                          onClick={() =>
                            onSelectConnector(connector.source_type)
                          }
                          data-testid={`kb-connector-${connector.source_type}`}
                        >
                          <ForwardedIconComponent
                            name={connector.icon ?? "Plug"}
                            className="mr-2 h-4 w-4"
                          />
                          {connector.display_name}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  {activeConnector && (
                    <div className="mt-3 rounded-md border border-border bg-background p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs font-medium">
                          <ForwardedIconComponent
                            name={activeConnectorEntry?.icon ?? "Plug"}
                            className="h-3.5 w-3.5"
                          />
                          {activeConnectorEntry?.display_name ??
                            activeConnector}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={() => onSelectConnector(null)}
                        >
                          Clear
                        </Button>
                      </div>
                      {activeConnector === "s3" && (
                        <S3ConnectorForm
                          onPayloadChange={onConnectorPayloadChange}
                        />
                      )}
                      {activeConnector === "google_drive" && (
                        <GoogleDriveConnectorForm
                          onPayloadChange={onConnectorPayloadChange}
                        />
                      )}
                      {activeConnector === "onedrive" && (
                        <OneDriveConnectorForm
                          onPayloadChange={onConnectorPayloadChange}
                        />
                      )}
                      {activeConnector === "sharepoint" && (
                        <SharePointConnectorForm
                          onPayloadChange={onConnectorPayloadChange}
                        />
                      )}
                    </div>
                  )}

                  {validationErrors.files && (
                    <span className="text-xs text-destructive">
                      {validationErrors.files}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  {/* <Label className="text-xs text-muted-foreground flex items-center gap-1">
                    Column Details
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help">
                            <ForwardedIconComponent
                              name="Info"
                              className="h-3.5 w-3.5 text-muted-foreground"
                            />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[260px]">
                          Configure column behavior for the knowledge base.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </Label>
                  <ColumnConfig
                    columnConfig={columnConfig}
                    onColumnConfigChange={onColumnConfigChange}
                  /> */}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Chunking Settings - Animated */}
        <div
          className={cn(
            "grid transition-all duration-300 ease-in-out",
            showAdvanced
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            <Separator className="my-4" />
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="Settings2"
                  className="h-4 w-4 text-muted-foreground"
                />
                <span className="text-sm font-medium">Chunking Settings</span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Chunk Size */}
                <div className="flex flex-col gap-2">
                  <Label
                    htmlFor="chunk-size"
                    className="flex items-center gap-1 text-xs text-muted-foreground"
                  >
                    Chunk Size
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help">
                            <ForwardedIconComponent
                              name="Info"
                              className="h-3.5 w-3.5 text-muted-foreground"
                            />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[260px]">
                          The maximum length of each chunk. Text is first split
                          by separator, then chunks are merged up to this size.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </Label>
                  <Input
                    id="chunk-size"
                    type="number"
                    value={chunkSize}
                    onChange={(e) =>
                      onChunkSizeChange(Number(e.target.value) || 0)
                    }
                    min={1}
                    max={10000}
                    data-testid="kb-chunk-size-input"
                  />
                </div>

                {/* Chunk Overlap */}
                <div className="flex flex-col gap-2">
                  <Label
                    htmlFor="chunk-overlap"
                    className="flex items-center gap-1 text-xs text-muted-foreground"
                  >
                    Chunk Overlap
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help">
                            <ForwardedIconComponent
                              name="Info"
                              className="h-3.5 w-3.5 text-muted-foreground"
                            />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[260px]">
                          Number of characters to overlap between chunks.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </Label>
                  <Input
                    id="chunk-overlap"
                    type="number"
                    value={chunkOverlap}
                    onChange={(e) =>
                      onChunkOverlapChange(Number(e.target.value) || 0)
                    }
                    min={0}
                    max={chunkSize - 1}
                    data-testid="kb-chunk-overlap-input"
                  />
                </div>
              </div>

              {/* Separator */}
              <div className="flex flex-col gap-2">
                <Label
                  htmlFor="separator"
                  className="flex items-center gap-1 text-xs text-muted-foreground"
                >
                  Separator
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-help">
                          <ForwardedIconComponent
                            name="Info"
                            className="h-3.5 w-3.5 text-muted-foreground"
                          />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-[260px]">
                        The character to split on. Use \n for newline. Examples:
                        \n\n for paragraphs, \n for lines, . for sentences.
                        Leave blank for no separator.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </Label>
                <Input
                  id="separator"
                  placeholder="\n"
                  value={separator}
                  onChange={(e) => onSeparatorChange(e.target.value)}
                  data-testid="kb-separator-input"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
