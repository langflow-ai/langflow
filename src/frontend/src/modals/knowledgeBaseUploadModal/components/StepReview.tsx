import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  type AvailableDBProviderId,
  getDBProviderOption,
} from "@/constants/dbProviderConstants";
import { cn } from "@/utils/utils";
import type { ChunkPreview } from "../types";
import { ChunkPreviewCard } from "./ChunkPreviewCard";
import type { MetadataPair } from "./MetadataEditor";
import { filterValidMetadataPairs } from "./metadataValidation";
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
  backendType: AvailableDBProviderId;
  metadataPairs?: MetadataPair[];
  perFileMetadata?: Record<string, MetadataPair[]>;
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
  backendType,
  metadataPairs = [],
  perFileMetadata = {},
}: StepReviewProps) {
  const { t } = useTranslation();
  const selectedBackend = getDBProviderOption(backendType);
  // Use the same validator that gates "Next Step" so the summary only
  // shows pairs the backend will actually accept.
  const populatedRunPairs = filterValidMetadataPairs(metadataPairs);
  const filesWithOverrides = Object.values(perFileMetadata).filter(
    (pairs) => filterValidMetadataPairs(pairs).length > 0,
  ).length;

  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* Chunk Preview Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="Layers"
            className="h-4 w-4 text-muted-foreground"
          />
          <span className="text-sm font-medium">{t("modal.chunkPreview")}</span>
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
              {t("knowledge.noFilesSelected")}
            </p>
          </div>
        ) : isGeneratingPreview ? (
          <div className="flex flex-col items-center justify-center p-8 h-full">
            <ForwardedIconComponent
              name="Loader2"
              className="mb-2 h-8 w-8 animate-spin text-muted-foreground"
            />
            <p className="text-sm text-muted-foreground">
              {t("knowledge.generatingPreview")}
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
              {t("knowledge.couldNotGeneratePreview")}
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
        <span className="text-sm font-medium">{t("knowledge.summary")}</span>
      </div>

      <div className="shrink-0">
        <SummaryItem
          icon="Type"
          label={t("knowledge.labelName")}
          value={sourceName}
        />
        <SummaryItem
          icon="Files"
          label={t("knowledge.files")}
          value={`${files.length} ${files.length !== 1 ? t("knowledge.files") : t("knowledge.file")} (${totalFileSize})`}
        />
        <SummaryItem
          icon="Ruler"
          label={t("knowledge.labelChunkSize")}
          value={`${chunkSize} ${t("knowledge.charsSuffix")}`}
        />
        <SummaryItem
          icon="Layers"
          label={t("knowledge.labelChunkOverlap")}
          value={`${chunkOverlap} ${t("knowledge.charsSuffix")}`}
        />
        <SummaryItem
          icon="SplitSquareHorizontal"
          label={t("knowledge.labelSeparator")}
          value={separator || t("knowledge.labelNone")}
        />
        <div className="flex items-center justify-between py-1.5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ForwardedIconComponent name="Cpu" className="h-4 w-4" />
            <span>{t("knowledge.embeddingModelLabel")}</span>
          </div>
          <div className="flex items-center gap-1.5">
            {selectedEmbeddingModel[0]?.icon && (
              <ForwardedIconComponent
                name={selectedEmbeddingModel[0].icon}
                className="h-3.5 w-3.5"
              />
            )}
            <span className="text-sm font-medium">
              {selectedEmbeddingModel[0]?.name ||
                t("knowledge.labelNotSelected")}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between py-1.5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ForwardedIconComponent name="Database" className="h-4 w-4" />
            <span>{t("knowledge.dbProviderLabel")}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ForwardedIconComponent
              name={selectedBackend.icon}
              className="h-3.5 w-3.5"
            />
            <span className="text-sm font-medium">{selectedBackend.label}</span>
          </div>
        </div>

        {(populatedRunPairs.length > 0 || filesWithOverrides > 0) && (
          <div
            className="flex items-start justify-between py-1.5"
            data-testid="kb-summary-metadata"
          >
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <ForwardedIconComponent name="Tag" className="h-4 w-4" />
              <span>{t("knowledge.metadataLabel")}</span>
            </div>
            <div className="flex max-w-[60%] flex-wrap justify-end gap-1">
              {populatedRunPairs.map((pair) => (
                <span
                  key={`${pair.key}=${pair.value}`}
                  className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs"
                  data-testid={`kb-summary-tag-${pair.key}`}
                >
                  <span className="font-medium text-muted-foreground">
                    {pair.key}:
                  </span>
                  <span className="ml-1">{pair.value}</span>
                </span>
              ))}
              {filesWithOverrides > 0 && (
                <span
                  className="inline-flex items-center rounded-full bg-accent-emerald/20 px-2 py-0.5 text-xs text-accent-emerald-foreground"
                  data-testid="kb-summary-per-file-count"
                >
                  {filesWithOverrides === 1
                    ? t("knowledge.oneFileOverride")
                    : t("knowledge.nFileOverrides", {
                        count: filesWithOverrides,
                      })}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
