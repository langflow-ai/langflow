import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelInputComponent, {
  type ModelOption,
} from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import { ACCEPTED_FILE_TYPES } from "../constants";

interface StepConfigurationProps {
  isAddSourcesMode: boolean;
  sourceName: string;
  onSourceNameChange: (value: string) => void;
  selectedEmbeddingModel: ModelOption[];
  onEmbeddingModelChange: (value: ModelOption[]) => void;
  embeddingModelOptions: ModelOption[];
  existingEmbeddingModel?: string;
  existingEmbeddingIcon?: string;
  chunkSize: number | undefined;
  onChunkSizeChange: (value: number | undefined) => void;
  chunkOverlap: number | undefined;
  onChunkOverlapChange: (value: number | undefined) => void;
  separator: string | undefined;
  onSeparatorChange: (value: string | undefined) => void;
  showAdvanced: boolean;
  toggleAdvanced: () => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFolderSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  validationErrors?: Record<string, string>;
  onFieldChange?: () => void;
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
}: StepConfigurationProps) {
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
          )}
        </div>

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
          className="hidden"
          onChange={onFolderSelect}
          {...({
            webkitdirectory: "",
            directory: "",
          } as React.HTMLAttributes<HTMLInputElement>)}
        />

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
                    className="text-xs text-muted-foreground"
                  >
                    Chunk Size
                  </Label>
                  <Input
                    id="chunk-size"
                    type="number"
                    value={chunkSize ?? ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      onChunkSizeChange(val === "" ? undefined : Number(val));
                    }}
                    placeholder="1000"
                    min={100}
                    max={10000}
                    data-testid="kb-chunk-size-input"
                  />
                </div>

                {/* Chunk Overlap */}
                <div className="flex flex-col gap-2">
                  <Label
                    htmlFor="chunk-overlap"
                    className="text-xs text-muted-foreground"
                  >
                    Chunk Overlap
                  </Label>
                  <Input
                    id="chunk-overlap"
                    type="number"
                    value={chunkOverlap ?? ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      onChunkOverlapChange(
                        val === "" ? undefined : Number(val),
                      );
                    }}
                    placeholder="200"
                    min={0}
                    max={(chunkSize ?? 1000) - 1}
                    data-testid="kb-chunk-overlap-input"
                  />
                </div>
              </div>

              {/* Separator */}
              <div className="flex flex-col gap-2">
                <Label
                  htmlFor="separator"
                  className="text-xs text-muted-foreground"
                >
                  Separator
                </Label>
                <Input
                  id="separator"
                  value={separator ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    onSeparatorChange(val === "" ? undefined : val);
                  }}
                  placeholder="\\n\\n"
                  data-testid="kb-separator-input"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Table Configure - Animated */}
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
                <span className="text-sm font-medium">Configure Sources</span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label className="text-xs text-muted-foreground">
                    Sources
                  </Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" className="w-full px-3">
                        <span className="flex items-center gap-2 mr-auto">
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
                    <DropdownMenuContent align="start" className="w-[200px]">
                      <DropdownMenuItem
                        onClick={() =>
                          document.getElementById("file-input")?.click()
                        }
                      >
                        <ForwardedIconComponent
                          name="FileText"
                          className="mr-2 h-4 w-4"
                        />
                        Upload Files
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() =>
                          document.getElementById("folder-input")?.click()
                        }
                      >
                        <ForwardedIconComponent
                          name="Folder"
                          className="mr-2 h-4 w-4"
                        />
                        Upload Folder
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="flex flex-col gap-2">
                  <Label className="text-xs text-muted-foreground">
                    Column Details
                  </Label>
                  <Button
                    variant="outline"
                    className="w-full justify-center"
                    onClick={toggleAdvanced}
                  >
                    <span className="flex items-center gap-2">
                      <ForwardedIconComponent
                        name="Columns"
                        className="h-4 w-4"
                      />
                      Open Table
                    </span>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
