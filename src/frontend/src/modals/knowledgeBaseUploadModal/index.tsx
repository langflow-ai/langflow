import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import ModelInputComponent, {
  type ModelOption,
} from '@/components/core/parameterRenderComponent/components/modelInputComponent';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { api } from '@/controllers/API/api';
import { getURL } from '@/controllers/API/helpers/constants';
import { useCreateKnowledgeBase } from '@/controllers/API/queries/knowledge-bases/use-create-knowledge-base';
import { useGetModelProviders } from '@/controllers/API/queries/models/use-get-model-providers';
import useAlertStore from '@/stores/alertStore';
import { cn } from '@/utils/utils';
import { StepperModal, StepperModalFooter } from '../stepperModal';

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

type WizardStep = 1 | 2;

const STEP_TITLES: Record<WizardStep, string> = {
  1: 'Create Knowledge Base',
  2: 'Review & Build',
};

const STEP_DESCRIPTIONS: Record<WizardStep, string> = {
  1: 'Name your knowledge base, upload sources, and select an embedding model',
  2: 'Preview how your files will be chunked and confirm your settings',
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
    <div className="flex flex-col rounded-lg border bg-muted/30 p-3 min-h-0 h-full">
      <div className="mb-2 flex items-center justify-between shrink-0">
        <span className="text-xs font-medium text-muted-foreground">
          Chunk {index + 1}
        </span>
      </div>
      <div className="overflow-y-auto rounded bg-background p-2 text-xs font-mono flex-1 min-h-0 whitespace-pre-wrap break-words">
        {chunk.content}
      </div>
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
    <div className="flex items-center justify-between py-1.5">
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
        if (model.metadata?.model_type !== 'embeddings') continue;
        options.push({
          id: model.model_name,
          name: model.model_name,
          icon: provider.icon || 'Bot',
          provider: provider.provider,
          metadata: model.metadata,
        });
      }
    }
    return options;
  }, [modelProviders]);

  // Form state - Step 1
  const [sourceName, setSourceName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [chunkSize, setChunkSize] = useState(1000);
  const [chunkOverlap, setChunkOverlap] = useState(200);
  const [separator, setSeparator] = useState('\\n\\n');

  // Form state - Step 3
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<
    ModelOption[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isFilePanelOpen, setIsFilePanelOpen] = useState(false);

  const toggleAdvanced = useCallback(() => {
    setShowAdvanced(prev => {
      if (prev) {
        // Hiding advanced: close panel but keep files
        setIsFilePanelOpen(false);
      }
      return !prev;
    });
  }, []);

  // Preview state - Step 2
  const [chunkPreviews, setChunkPreviews] = useState<ChunkPreview[]>([]);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
  const [selectedPreviewFileIndex, setSelectedPreviewFileIndex] = useState(0);

  // Alert store
  const setSuccessData = useAlertStore(state => state.setSuccessData);
  const setErrorData = useAlertStore(state => state.setErrorData);

  // Create knowledge base mutation
  const createKnowledgeBase = useCreateKnowledgeBase();

  // Initialize form with existing knowledge base data when in Add Sources mode
  useEffect(() => {
    if (existingKnowledgeBase && open) {
      setSourceName(existingKnowledgeBase.name);
      if (existingKnowledgeBase.embeddingModel) {
        const matchingModel = embeddingModelOptions.find(
          opt => opt.id === existingKnowledgeBase.embeddingModel
        );
        if (matchingModel) {
          setSelectedEmbeddingModel([matchingModel]);
        }
      }
    }
  }, [existingKnowledgeBase, open, embeddingModelOptions]);

  const resetForm = useCallback(() => {
    setSourceName('');
    setFiles([]);
    setChunkSize(1000);
    setChunkOverlap(200);
    setSeparator('\\n\\n');
    setSelectedEmbeddingModel([]);
    setChunkPreviews([]);
    setCurrentChunkIndex(0);
    setSelectedPreviewFileIndex(0);
    setCurrentStep(1);
    setIsFilePanelOpen(false);
  }, []);

  // Generate chunk previews (client-side simulation) - up to 3 chunks per file
  const generateChunkPreviews = useCallback(async () => {
    if (files.length === 0) {
      setChunkPreviews([]);
      return;
    }

    setIsGeneratingPreview(true);

    try {
      const allPreviews: ChunkPreview[] = [];
      const actualSeparator = separator
        .replace(/\\n/g, '\n')
        .replace(/\\t/g, '\t');

      const filesToProcess = [
        files[selectedPreviewFileIndex] || files[0],
      ].filter(Boolean);

      for (const file of filesToProcess) {
        const text = await file.text();

        // Simple chunking simulation
        let chunks: string[] = [];
        const separatorChunks = actualSeparator
          ? text.split(actualSeparator).filter(c => c.trim())
          : [];
        if (separatorChunks.length > 1) {
          chunks = separatorChunks;
        } else {
          const step = Math.max(1, chunkSize - chunkOverlap);
          for (let i = 0; i < text.length; i += step) {
            chunks.push(text.slice(i, i + chunkSize));
          }
        }

        // Take up to 3 chunks per file
        const previewChunks = chunks.slice(0, 3);
        let position = 0;

        for (let i = 0; i < previewChunks.length; i++) {
          const chunk = previewChunks[i];
          if (chunk.trim()) {
            allPreviews.push({
              content: chunk.trim().slice(0, chunkSize),
              index: allPreviews.length,
              metadata: {
                source: file.name,
                start: position,
                end: position + chunk.length,
              },
            });
          }
          position += chunk.length + actualSeparator.length;
        }
      }

      setChunkPreviews(allPreviews);
    } catch (error) {
      console.error('Error generating preview:', error);
      setChunkPreviews([]);
    } finally {
      setIsGeneratingPreview(false);
    }
  }, [files, chunkSize, chunkOverlap, separator, selectedPreviewFileIndex]);

  // Generate previews when entering step 2
  useEffect(() => {
    if (currentStep === 2) {
      generateChunkPreviews();
    }
  }, [currentStep, generateChunkPreviews]);

  const handleSubmit = async () => {
    if (!selectedEmbeddingModel.length) {
      setErrorData({ title: 'Please select an embedding model' });
      return;
    }

    const selectedModel = selectedEmbeddingModel[0];
    const kbName = sourceName.trim().replace(/\s+/g, '_');
    setIsSubmitting(true);

    try {
      // Create the knowledge base (skip if adding to existing)
      if (!isAddSourcesMode) {
        await createKnowledgeBase.mutateAsync({
          name: kbName,
          embedding_provider: selectedModel.provider || 'Unknown',
          embedding_model: selectedModel.id || selectedModel.name,
        });
      }

      // Upload and ingest files
      let ingestResult: any = null;
      if (files.length > 0) {
        try {
          const formData = new FormData();
          files.forEach(file => {
            formData.append('files', file);
          });
          formData.append('source_name', sourceName);
          formData.append('chunk_size', chunkSize.toString());
          formData.append('chunk_overlap', chunkOverlap.toString());
          formData.append('separator', separator);

          const response = await api.post(
            `${getURL('KNOWLEDGE_BASES')}/${kbName}/ingest`,
            formData,
            {
              headers: { 'Content-Type': 'multipart/form-data' },
            }
          );
          ingestResult = response.data;
        } catch (ingestError: any) {
          console.warn('Failed to ingest files:', ingestError);
          if (!isAddSourcesMode) {
            setSuccessData({
              title: `Knowledge base "${sourceName}" created, but file ingestion failed. You can add files later.`,
            });
          } else {
            setErrorData({
              title: 'Failed to add sources to knowledge base',
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
        'Failed to create knowledge base';
      setErrorData({ title: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles(prev => [...prev, ...Array.from(selectedFiles)]);
      setIsFilePanelOpen(true);
    }
    e.target.value = '';
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles(prev => [...prev, ...Array.from(selectedFiles)]);
      setIsFilePanelOpen(true);
    }
    e.target.value = '';
  };

  const handleRemoveFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Validation
  const isStep1Valid =
    sourceName.trim() !== '' &&
    (isAddSourcesMode || selectedEmbeddingModel.length > 0);
  const isStep2Valid = true; // Review step is always valid

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return isStep1Valid;
      case 2:
        return isStep2Valid;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < 2) {
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
                  onChange={e => setSourceName(e.target.value)}
                  data-testid="kb-source-name-input"
                  disabled={isAddSourcesMode}
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
                      name={selectedEmbeddingModel[0]?.icon || 'Cpu'}
                      className="h-4 w-4 shrink-0"
                    />
                    <span className="text-muted-foreground">
                      {existingKnowledgeBase?.embeddingModel || 'Unknown'}
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
                {...({ webkitdirectory: '', directory: '' } as any)}
              />

              {/* Chunking Settings - Animated */}
              <div
                className={cn(
                  'grid transition-all duration-300 ease-in-out',
                  showAdvanced
                    ? 'grid-rows-[1fr] opacity-100'
                    : 'grid-rows-[0fr] opacity-0'
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
                      <span className="text-sm font-medium">
                        Chunking Settings
                      </span>
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
                          value={chunkSize}
                          onChange={e => setChunkSize(Number(e.target.value))}
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
                          value={chunkOverlap}
                          onChange={e =>
                            setChunkOverlap(Number(e.target.value))
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
                        className="text-xs text-muted-foreground"
                      >
                        Separator
                      </Label>
                      <Input
                        id="separator"
                        value={separator}
                        onChange={e => setSeparator(e.target.value)}
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
                  'grid transition-all duration-300 ease-in-out',
                  showAdvanced
                    ? 'grid-rows-[1fr] opacity-100'
                    : 'grid-rows-[0fr] opacity-0'
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
                      </span>
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
                          <DropdownMenuContent
                            align="start"
                            className="w-[200px]"
                          >
                            <DropdownMenuItem
                              onClick={() =>
                                document.getElementById('file-input')?.click()
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
                                document.getElementById('folder-input')?.click()
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

      case 2:
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
                          {files[selectedPreviewFileIndex]?.name ??
                            files[0]?.name}
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
                            setSelectedPreviewFileIndex(idx);
                            setCurrentChunkIndex(0);
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
                  disabled={
                    chunkPreviews.length === 0 || currentChunkIndex === 0
                  }
                  onClick={() => setCurrentChunkIndex(prev => prev - 1)}
                >
                  <ForwardedIconComponent
                    name="ChevronLeft"
                    className={cn(
                      'h-4 w-4',
                      chunkPreviews.length === 0 || currentChunkIndex === 0
                        ? 'text-muted-foreground/40'
                        : 'text-foreground'
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
                  onClick={() => setCurrentChunkIndex(prev => prev + 1)}
                >
                  <ForwardedIconComponent
                    name="ChevronRight"
                    className={cn(
                      'h-4 w-4',
                      chunkPreviews.length === 0 ||
                        currentChunkIndex === chunkPreviews.length - 1
                        ? 'text-muted-foreground/40'
                        : 'text-foreground'
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
                value={`${files.length} file${files.length !== 1 ? 's' : ''} (${totalFileSize})`}
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
                value={separator || 'None'}
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
                    {selectedEmbeddingModel[0]?.name || 'Not selected'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
    }
  };

  // Files side panel content
  const filesPanelContent = (
    <>
      {/* Panel Content - File List */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="flex items-center gap-2 text-base font-semibold my-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
            <ForwardedIconComponent name="FileStack" className="h-4 w-4" />
          </div>
          Sources
        </div>
        <div className="flex flex-col gap-1">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="group flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted"
            >
              <div className="flex items-center gap-2 truncate">
                <ForwardedIconComponent
                  name="FileText"
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                />
                <span className="truncate text-sm">{file.name}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                onClick={() => handleRemoveFile(index)}
              >
                <ForwardedIconComponent name="X" className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </>
  );

  return (
    <StepperModal
      open={open}
      onOpenChange={isOpen => {
        setOpen(isOpen);
        if (!isOpen) resetForm();
      }}
      className="bg-background"
      contentClassName="bg-muted"
      currentStep={currentStep}
      totalSteps={2}
      title={isAddSourcesMode ? 'Add Sources' : STEP_TITLES[currentStep]}
      description={STEP_DESCRIPTIONS[currentStep]}
      icon="Database"
      height={showAdvanced ? 'h-[690px]' : 'h-[347px]'}
      width="w-[700px]"
      showProgress={false}
      sidePanel={filesPanelContent}
      sidePanelOpen={showAdvanced && files.length > 0}
      footer={
        <StepperModalFooter
          currentStep={currentStep}
          totalSteps={showAdvanced ? 2 : 1}
          onBack={handleBack}
          onNext={handleNext}
          onSubmit={handleSubmit}
          nextDisabled={!canProceed()}
          submitDisabled={!canProceed()}
          isSubmitting={isSubmitting}
          submitLabel={isAddSourcesMode ? 'Add Sources' : 'Create'}
          helpLabel={
            currentStep === 1
              ? showAdvanced
                ? 'Hide Advanced'
                : 'Advanced'
              : undefined
          }
          onHelp={currentStep === 1 ? toggleAdvanced : undefined}
        />
      }
    >
      {renderStepContent()}
    </StepperModal>
  );
}
