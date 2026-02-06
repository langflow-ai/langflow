import { useCallback, useEffect, useMemo, useState } from "react";
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
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useCreateKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { StepperModal, StepperModalFooter } from "../stepperModal";

// Types
export interface KnowledgeBaseUploadModalProps {
  open?: boolean;
  setOpen?: (open: boolean) => void;
  onSubmit?: (data: KnowledgeBaseFormData) => void;
  onOpenExampleFlow?: () => void;
  existingKnowledgeBase?: {
    name: string;
    embeddingProvider?: string;
    embeddingModel?: string;
  };
}

export interface KnowledgeBaseFormData {
  sourceName: string;
  files: File[];
  embeddingModel: ModelOption[] | null;
  chunkSize: number;
  chunkOverlap: number;
  separator: string;
}

interface ChunkPreview {
  content: string;
  index: number;
  metadata: {
    source: string;
    start: number;
    end: number;
  };
}

type WizardStep = 1 | 2 | 3;

const STEP_TITLES: Record<WizardStep, string> = {
  1: "Configure Sources",
  2: "Preview Chunks",
  3: "Select Model & Create",
};

const STEP_DESCRIPTIONS: Record<WizardStep, string> = {
  1: "Add files and configure chunking settings",
  2: "Review how your documents will be split into chunks",
  3: "Choose an embedding model and create your knowledge base",
};

// Chunk preview card component
function ChunkPreviewCard({
  chunk,
  index,
}: {
  chunk: ChunkPreview;
  index: number;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          Chunk {index + 1}
        </span>
        <span className="text-xs text-muted-foreground">
          {chunk.content.length} chars
        </span>
      </div>
      <div className="max-h-[100px] overflow-y-auto rounded bg-background p-2 text-xs font-mono">
        {chunk.content.slice(0, 300)}
        {chunk.content.length > 300 && (
          <span className="text-muted-foreground">...</span>
        )}
      </div>
      {chunk.metadata.source && (
        <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
          <ForwardedIconComponent name="FileText" className="h-3 w-3" />
          <span className="truncate">{chunk.metadata.source}</span>
        </div>
      )}
    </div>
  );
}

// Summary item component
function SummaryItem({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <ForwardedIconComponent name={icon} className="h-4 w-4" />
        <span>{label}</span>
      </div>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export default function KnowledgeBaseUploadModal({
  open: controlledOpen,
  setOpen: controlledSetOpen,
  onSubmit,
  onOpenExampleFlow,
  existingKnowledgeBase,
}: KnowledgeBaseUploadModalProps) {
  const isAddSourcesMode = !!existingKnowledgeBase;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledSetOpen ?? setInternalOpen;

  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);

  // Fetch embedding model data from API
  const { data: modelProviders = [] } = useGetModelProviders({});

  // Transform provider data into ModelOption[] for embedding models only
  const embeddingModelOptions = useMemo<ModelOption[]>(() => {
    const options: ModelOption[] = [];
    for (const provider of modelProviders) {
      if (!provider.is_enabled) continue;
      for (const model of provider.models) {
        if (model.metadata?.model_type !== "embeddings") continue;
        options.push({
          id: model.model_name,
          name: model.model_name,
          icon: provider.icon || "Bot",
          provider: provider.provider,
          metadata: model.metadata,
        });
      }
    }
    return options;
  }, [modelProviders]);

  // Form state - Step 1
  const [sourceName, setSourceName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [chunkSize, setChunkSize] = useState(1000);
  const [chunkOverlap, setChunkOverlap] = useState(200);
  const [separator, setSeparator] = useState("\\n\\n");

  // Form state - Step 3
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<
    ModelOption[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Preview state - Step 2
  const [chunkPreviews, setChunkPreviews] = useState<ChunkPreview[]>([]);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);

  // Alert store
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Create knowledge base mutation
  const createKnowledgeBase = useCreateKnowledgeBase();

  // Initialize form with existing knowledge base data when in Add Sources mode
  useEffect(() => {
    if (existingKnowledgeBase && open) {
      setSourceName(existingKnowledgeBase.name);
      if (existingKnowledgeBase.embeddingModel) {
        const matchingModel = embeddingModelOptions.find(
          (opt) => opt.id === existingKnowledgeBase.embeddingModel,
        );
        if (matchingModel) {
          setSelectedEmbeddingModel([matchingModel]);
        }
      }
    }
  }, [existingKnowledgeBase, open, embeddingModelOptions]);

  const resetForm = useCallback(() => {
    setSourceName("");
    setFiles([]);
    setChunkSize(1000);
    setChunkOverlap(200);
    setSeparator("\\n\\n");
    setSelectedEmbeddingModel([]);
    setChunkPreviews([]);
    setCurrentStep(1);
  }, []);

  // Generate chunk previews (client-side simulation)
  const generateChunkPreviews = useCallback(async () => {
    if (files.length === 0) {
      setChunkPreviews([]);
      return;
    }

    setIsGeneratingPreview(true);

    try {
      const previews: ChunkPreview[] = [];
      const actualSeparator = separator
        .replace(/\\n/g, "\n")
        .replace(/\\t/g, "\t");

      // Read first file for preview
      const file = files[0];
      const text = await file.text();

      // Simple chunking simulation
      let chunks: string[] = [];
      if (actualSeparator) {
        chunks = text.split(actualSeparator);
      } else {
        // Character-based chunking
        for (let i = 0; i < text.length; i += chunkSize - chunkOverlap) {
          chunks.push(text.slice(i, i + chunkSize));
        }
      }

      // Take first 3 chunks for preview
      const previewChunks = chunks.slice(0, 3);
      let position = 0;

      for (let i = 0; i < previewChunks.length; i++) {
        const chunk = previewChunks[i];
        if (chunk.trim()) {
          previews.push({
            content: chunk.trim().slice(0, chunkSize),
            index: i,
            metadata: {
              source: file.name,
              start: position,
              end: position + chunk.length,
            },
          });
        }
        position += chunk.length + actualSeparator.length;
      }

      setChunkPreviews(previews);
    } catch (error) {
      console.error("Error generating preview:", error);
      setChunkPreviews([]);
    } finally {
      setIsGeneratingPreview(false);
    }
  }, [files, chunkSize, chunkOverlap, separator]);

  // Generate previews when entering step 2
  useEffect(() => {
    if (currentStep === 2) {
      generateChunkPreviews();
    }
  }, [currentStep, generateChunkPreviews]);

  const handleSubmit = async () => {
    if (!selectedEmbeddingModel.length) {
      setErrorData({ title: "Please select an embedding model" });
      return;
    }

    const selectedModel = selectedEmbeddingModel[0];
    const kbName = sourceName.trim().replace(/\s+/g, "_");
    setIsSubmitting(true);

    try {
      // Create the knowledge base (skip if adding to existing)
      if (!isAddSourcesMode) {
        await createKnowledgeBase.mutateAsync({
          name: kbName,
          embedding_provider: selectedModel.provider || "Unknown",
          embedding_model: selectedModel.id || selectedModel.name,
        });
      }

      // Upload and ingest files
      let ingestResult: any = null;
      if (files.length > 0) {
        try {
          const formData = new FormData();
          files.forEach((file) => {
            formData.append("files", file);
          });
          formData.append("source_name", sourceName);
          formData.append("chunk_size", chunkSize.toString());
          formData.append("chunk_overlap", chunkOverlap.toString());
          formData.append("separator", separator);

          const response = await api.post(
            `${getURL("KNOWLEDGE_BASES")}/${kbName}/ingest`,
            formData,
            {
              headers: { "Content-Type": "multipart/form-data" },
            },
          );
          ingestResult = response.data;
        } catch (ingestError: any) {
          console.warn("Failed to ingest files:", ingestError);
          if (!isAddSourcesMode) {
            setSuccessData({
              title: `Knowledge base "${sourceName}" created, but file ingestion failed. You can add files later.`,
            });
          } else {
            setErrorData({
              title: "Failed to add sources to knowledge base",
            });
          }
          onSubmit?.({
            sourceName,
            files,
            embeddingModel: selectedEmbeddingModel,
            chunkSize,
            chunkOverlap,
            separator,
          });
          setOpen(false);
          resetForm();
          return;
        }
      }

      const callbackData: KnowledgeBaseFormData = {
        sourceName,
        files,
        embeddingModel: selectedEmbeddingModel,
        chunkSize,
        chunkOverlap,
        separator,
      };

      if (isAddSourcesMode) {
        const chunksCreated = ingestResult?.chunks_created || 0;
        setSuccessData({
          title: `Added ${files.length} file(s) with ${chunksCreated} chunks to "${sourceName}"!`,
        });
      } else if (files.length > 0) {
        const chunksCreated = ingestResult?.chunks_created || 0;
        setSuccessData({
          title: `Knowledge base "${sourceName}" created with ${files.length} file(s) and ${chunksCreated} chunks!`,
        });
      } else {
        setSuccessData({
          title: `Knowledge base "${sourceName}" created! You can add files later.`,
        });
      }

      onSubmit?.(callbackData);
      setOpen(false);
      resetForm();
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to create knowledge base";
      setErrorData({ title: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(selectedFiles)]);
    }
    e.target.value = "";
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(selectedFiles)]);
    }
    e.target.value = "";
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Validation
  const isStep1Valid = sourceName.trim() !== "";
  const isStep2Valid = true; // Preview step is always valid
  const isStep3Valid = selectedEmbeddingModel.length > 0;

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return isStep1Valid;
      case 2:
        return isStep2Valid;
      case 3:
        return isStep3Valid;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < 3) {
      setCurrentStep((currentStep + 1) as WizardStep);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((currentStep - 1) as WizardStep);
    }
  };

  const totalFileSize = useMemo(() => {
    const bytes = files.reduce((acc, file) => acc + file.size, 0);
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }, [files]);

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="flex flex-col gap-4">
            {/* Name and Sources - side by side */}
            <div className="grid grid-cols-6 gap-4">
              <div className="col-span-4 flex flex-col gap-2">
                <Label htmlFor="source-name" className="text-sm font-medium">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="source-name"
                  placeholder="Enter a name for this knowledge base"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  data-testid="kb-source-name-input"
                  disabled={isAddSourcesMode}
                />
              </div>

              <div className="col-span-2 flex flex-col gap-2 w-full">
                <Label className="text-sm font-medium">Sources</Label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full justify-between"
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
            </div>

            {/* Hidden file inputs */}
            <input
              id="file-input"
              type="file"
              multiple
              className="hidden"
              onChange={handleFileSelect}
              accept=".pdf,.txt,.md,.docx,.doc,.csv,.json,.html,.xml"
            />
            <input
              id="folder-input"
              type="file"
              className="hidden"
              onChange={handleFolderSelect}
              {...({ webkitdirectory: "", directory: "" } as any)}
            />

            {/* Selected Files List */}
            {files.length > 0 && (
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ForwardedIconComponent
                      name="Files"
                      className="h-4 w-4 text-muted-foreground"
                    />
                    <span className="text-sm font-medium">
                      {files.length} file{files.length > 1 ? "s" : ""} (
                      {totalFileSize})
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setFiles([])}
                  >
                    <ForwardedIconComponent name="X" className="mr-1 h-3 w-3" />
                    Clear
                  </Button>
                </div>
                <div className="max-h-[100px] overflow-y-auto text-sm text-muted-foreground">
                  {files.slice(0, 5).map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="group flex items-center justify-between truncate py-0.5"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <ForwardedIconComponent
                          name="FileText"
                          className="h-3 w-3 shrink-0"
                        />
                        <span className="truncate">{file.name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={() => handleRemoveFile(index)}
                      >
                        <ForwardedIconComponent name="X" className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                  {files.length > 5 && (
                    <div className="py-0.5 text-xs">
                      +{files.length - 5} more files
                    </div>
                  )}
                </div>
              </div>
            )}

            <Separator className="" />

            {/* Chunking Settings */}
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
                    Chunk Size (characters)
                  </Label>
                  <Input
                    id="chunk-size"
                    type="number"
                    value={chunkSize}
                    onChange={(e) => setChunkSize(Number(e.target.value))}
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
                    Chunk Overlap (characters)
                  </Label>
                  <Input
                    id="chunk-overlap"
                    type="number"
                    value={chunkOverlap}
                    onChange={(e) => setChunkOverlap(Number(e.target.value))}
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
                  className="text-xs text-muted-foreground"
                >
                  Separator (use \n for newline, \t for tab)
                </Label>
                <Input
                  id="separator"
                  value={separator}
                  onChange={(e) => setSeparator(e.target.value)}
                  placeholder="\\n\\n"
                  data-testid="kb-separator-input"
                />
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="Layers"
                  className="h-4 w-4 text-muted-foreground"
                />
                <span className="text-sm font-medium">Chunk Preview</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={generateChunkPreviews}
                disabled={isGeneratingPreview || files.length === 0}
              >
                <ForwardedIconComponent
                  name="RefreshCw"
                  className={cn(
                    "mr-1 h-3 w-3",
                    isGeneratingPreview && "animate-spin",
                  )}
                />
                Refresh
              </Button>
            </div>

            {files.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
                <ForwardedIconComponent
                  name="FileQuestion"
                  className="mb-2 h-8 w-8 text-muted-foreground"
                />
                <p className="text-sm text-muted-foreground">
                  No files selected. Go back to add files.
                </p>
              </div>
            ) : isGeneratingPreview ? (
              <div className="flex flex-col items-center justify-center p-8">
                <ForwardedIconComponent
                  name="Loader2"
                  className="mb-2 h-8 w-8 animate-spin text-muted-foreground"
                />
                <p className="text-sm text-muted-foreground">
                  Generating preview...
                </p>
              </div>
            ) : chunkPreviews.length > 0 ? (
              <div className="flex flex-col gap-3">
                {chunkPreviews.map((chunk, index) => (
                  <ChunkPreviewCard key={index} chunk={chunk} index={index} />
                ))}
                <p className="text-center text-xs text-muted-foreground">
                  Showing first {chunkPreviews.length} chunk
                  {chunkPreviews.length > 1 ? "s" : ""} from "{files[0]?.name}"
                </p>
              </div>
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

            {/* Settings Summary */}
            <div className="rounded-lg bg-muted/50 p-3">
              <span className="text-xs font-medium text-muted-foreground">
                Current Settings
              </span>
              <div className="mt-2 flex gap-4 text-xs">
                <span>
                  Chunk Size: <strong>{chunkSize}</strong>
                </span>
                <span>
                  Overlap: <strong>{chunkOverlap}</strong>
                </span>
                <span>
                  Separator: <strong>{separator || "(none)"}</strong>
                </span>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="flex flex-col gap-4">
            {/* Summary Section */}
            <div className="rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2">
                <ForwardedIconComponent
                  name="FileStack"
                  className="h-4 w-4 text-muted-foreground"
                />
                <span className="text-sm font-medium">Summary</span>
              </div>
              <Separator className="mb-3" />
              <div className="space-y-1">
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
                  value={separator || "(none)"}
                />
              </div>
            </div>

            {/* Model Selection */}
            <div className="flex flex-col gap-2">
              <Label className="text-sm font-medium">
                Embedding Model <span className="text-destructive">*</span>
              </Label>
              {isAddSourcesMode ? (
                <div className="flex h-10 w-full items-center gap-2 rounded-md border border-input bg-muted px-3 py-2 text-sm">
                  <ForwardedIconComponent
                    name={selectedEmbeddingModel[0]?.icon || "Cpu"}
                    className="h-4 w-4 shrink-0"
                  />
                  <span className="text-muted-foreground">
                    {existingKnowledgeBase?.embeddingModel || "Unknown"}
                  </span>
                </div>
              ) : (
                <ModelInputComponent
                  id="kb-embedding-model"
                  value={selectedEmbeddingModel}
                  editNode={false}
                  disabled={false}
                  handleOnNewValue={({ value }) =>
                    setSelectedEmbeddingModel(value)
                  }
                  options={embeddingModelOptions}
                  placeholder="Select embedding model"
                  showEmptyState
                />
              )}
              <p className="text-xs text-muted-foreground">
                The embedding model determines how your documents are converted
                to vectors for semantic search.
              </p>
            </div>
          </div>
        );
    }
  };

  return (
    <StepperModal
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) resetForm();
      }}
      className="bg-secondary"
      currentStep={currentStep}
      totalSteps={3}
      title={isAddSourcesMode ? "Add Sources" : STEP_TITLES[currentStep]}
      description={STEP_DESCRIPTIONS[currentStep]}
      icon="Database"
      size="small-h-full"
      footer={
        <StepperModalFooter
          currentStep={currentStep}
          totalSteps={3}
          onBack={handleBack}
          onNext={handleNext}
          onSubmit={handleSubmit}
          nextDisabled={!canProceed()}
          submitDisabled={!canProceed()}
          isSubmitting={isSubmitting}
          submitLabel={isAddSourcesMode ? "Add Sources" : "Create"}
        />
      }
    >
      {renderStepContent()}
    </StepperModal>
  );
}
