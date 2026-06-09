import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import type { ChunkPreview } from "../types";
import { ChunkPreviewCard } from "./ChunkPreviewCard";
import { SummaryItem } from "./SummaryItem";

interface StepReviewProps {
  files: File[];
  chunkPreviews: ChunkPreview[];
  isGeneratingPreview: boolean;
  currentChunkIndex: number;
  onCurrentChunkIndexChange: (index: number) => void;
  selectedPreviewFileIndex: number;
  onSelectedPreviewFileIndexChange: (index: number) => void;
  sourceName: string;
  totalFileSize: string;
  chunkSize: number;
  chunkOverlap: number;
  separator: string;
  selectedEmbeddingModel: ModelOption[];
}

export function StepReview({
  files,
  chunkPreviews,
  isGeneratingPreview,
  currentChunkIndex,
  onCurrentChunkIndexChange,
  selectedPreviewFileIndex,
  onSelectedPreviewFileIndexChange,
  sourceName,
  totalFileSize,
  chunkSize,
  chunkOverlap,
  separator,
  selectedEmbeddingModel,
}: StepReviewProps) {
  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* Chunk Preview Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="Layers"
            className="h-4 w-4 text-muted-foreground"
          />
          <span className="text-sm font-medium">Chunk Preview</span>
        </div>
        <div className="flex items-center gap-1">
          {files.length > 1 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 max-w-[160px] text-xs"
                >
                  <span className="truncate">
                    {files[selectedPreviewFileIndex]?.name ?? files[0]?.name}
                  </span>
                  <ForwardedIconComponent
                    name="ChevronDown"
                    className="ml-1 h-3 w-3 shrink-0"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="max-w-[160px] overflow-y-auto"
              >
                {files.map((file, idx) => (
                  <DropdownMenuItem
                    key={`${file.name}-${idx}`}
                    onClick={() => {
                      onSelectedPreviewFileIndexChange(idx);
                      onCurrentChunkIndexChange(0);
                    }}
                  >
                    <span className="truncate text-xs">{file.name}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 rounded-md hover:bg-accent"
            disabled={chunkPreviews.length === 0 || currentChunkIndex === 0}
            onClick={() => onCurrentChunkIndexChange(currentChunkIndex - 1)}
          >
            <ForwardedIconComponent
              name="ChevronLeft"
              className={cn(
                "h-4 w-4",
                chunkPreviews.length === 0 || currentChunkIndex === 0
                  ? "text-muted-foreground/40"
                  : "text-foreground",
              )}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 rounded-md hover:bg-accent"
            disabled={
              chunkPreviews.length === 0 ||
              currentChunkIndex === chunkPreviews.length - 1
            }
            onClick={() => onCurrentChunkIndexChange(currentChunkIndex + 1)}
          >
            <ForwardedIconComponent
              name="ChevronRight"
              className={cn(
                "h-4 w-4",
                chunkPreviews.length === 0 ||
                  currentChunkIndex === chunkPreviews.length - 1
                  ? "text-muted-foreground/40"
                  : "text-foreground",
              )}
            />
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center h-full">
            <ForwardedIconComponent
              name="FileQuestion"
              className="mb-2 h-8 w-8 text-muted-foreground"
            />
            <p className="text-sm text-muted-foreground">
              No files selected. Go back to add files.
            </p>
          </div>
        ) : isGeneratingPreview ? (
          <div className="flex flex-col items-center justify-center p-8 h-full">
            <ForwardedIconComponent
              name="Loader2"
              className="mb-2 h-8 w-8 animate-spin text-muted-foreground"
            />
            <p className="text-sm text-muted-foreground">
              Generating preview...
            </p>
          </div>
        ) : chunkPreviews.length > 0 ? (
          <ChunkPreviewCard
            key={currentChunkIndex}
            chunk={chunkPreviews[currentChunkIndex]}
            index={currentChunkIndex}
          />
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
            <ForwardedIconComponent
              name="AlertCircle"
              className="mb-2 h-8 w-8 text-muted-foreground"
            />
            <p className="text-sm text-muted-foreground">
              Could not generate preview. Try adjusting your settings.
            </p>
          </div>
        )}
      </div>

      {/* Summary Section */}
      <div className="flex items-center gap-2 shrink-0">
        <ForwardedIconComponent
          name="FileStack"
          className="h-4 w-4 text-muted-foreground"
        />
        <span className="text-sm font-medium">Summary</span>
      </div>

      <div className="shrink-0">
        <SummaryItem icon="Type" label="Name" value={sourceName} />
        <SummaryItem
          icon="Files"
          label="Files"
          value={`${files.length} file${files.length !== 1 ? "s" : ""} (${totalFileSize})`}
        />
        <SummaryItem
          icon="Ruler"
          label="Chunk Size"
          value={`${chunkSize} chars`}
        />
        <SummaryItem
          icon="Layers"
          label="Chunk Overlap"
          value={`${chunkOverlap} chars`}
        />
        <SummaryItem
          icon="SplitSquareHorizontal"
          label="Separator"
          value={separator || "None"}
        />
        <div className="flex items-center justify-between py-1.5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ForwardedIconComponent name="Cpu" className="h-4 w-4" />
            <span>Embedding Model</span>
          </div>
          <div className="flex items-center gap-1.5">
            {selectedEmbeddingModel[0]?.icon && (
              <ForwardedIconComponent
                name={selectedEmbeddingModel[0].icon}
                className="h-3.5 w-3.5"
              />
            )}
            <span className="text-sm font-medium">
              {selectedEmbeddingModel[0]?.name || "Not selected"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
