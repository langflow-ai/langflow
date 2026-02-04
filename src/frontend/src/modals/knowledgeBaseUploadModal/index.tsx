import { type ReactNode, useMemo, useState } from 'react';
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
import { api } from '@/controllers/API/api';
import { getURL } from '@/controllers/API/helpers/constants';
import { useCreateKnowledgeBase } from '@/controllers/API/queries/knowledge-bases/use-create-knowledge-base';
import { useGetModelProviders } from '@/controllers/API/queries/models/use-get-model-providers';
import useAlertStore from '@/stores/alertStore';
import BaseModal from '../baseModal';

export interface KnowledgeBaseUploadModalProps {
  children?: ReactNode;
  open?: boolean;
  setOpen?: (open: boolean) => void;
  onSubmit?: (data: KnowledgeBaseFormData) => void;
  onOpenExampleFlow?: () => void;
}

export interface KnowledgeBaseFormData {
  sourceName: string;
  files: File[];
  embeddingModel: ModelOption[] | null;
}

export default function KnowledgeBaseUploadModal({
  children,
  open: controlledOpen,
  setOpen: controlledSetOpen,
  onSubmit,
  onOpenExampleFlow,
}: KnowledgeBaseUploadModalProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledSetOpen ?? setInternalOpen;

  // Fetch real embedding model data from API
  const { data: modelProviders = [], isLoading: isLoadingModels } =
    useGetModelProviders({});

  // Transform provider data into ModelOption[] for embedding models only
  const embeddingModelOptions = useMemo<ModelOption[]>(() => {
    const options: ModelOption[] = [];

    for (const provider of modelProviders) {
      // Only include enabled providers
      if (!provider.is_enabled) continue;

      for (const model of provider.models) {
        // Only include embedding models
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

  // Form state
  const [sourceName, setSourceName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<
    ModelOption[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);

  // Check if any providers with embedding models are enabled
  const hasEnabledEmbeddingProviders = useMemo(() => {
    return embeddingModelOptions.length > 0;
  }, [embeddingModelOptions]);

  // Alert store for notifications
  const setSuccessData = useAlertStore(state => state.setSuccessData);
  const setErrorData = useAlertStore(state => state.setErrorData);

  // Create knowledge base mutation
  const createKnowledgeBase = useCreateKnowledgeBase();

  const resetForm = () => {
    setSourceName('');
    setFiles([]);
    setSelectedEmbeddingModel([]);
  };

  const handleSubmit = async () => {
    if (!selectedEmbeddingModel.length) {
      setErrorData({ title: 'Please select an embedding model' });
      return;
    }

    const selectedModel = selectedEmbeddingModel[0];
    const kbName = sourceName.trim().replace(/\s+/g, '_');
    setIsSubmitting(true);

    try {
      // Step 1: Create the knowledge base
      await createKnowledgeBase.mutateAsync({
        name: kbName,
        embedding_provider: selectedModel.provider || 'Unknown',
        embedding_model: selectedModel.id || selectedModel.name,
      });

      // Step 2: Upload and ingest files directly to the knowledge base
      let ingestResult: any = null;
      if (files.length > 0) {
        try {
          // Create FormData with all files
          const formData = new FormData();
          files.forEach(file => {
            formData.append('files', file);
          });
          formData.append('source_name', sourceName);

          // Call the ingest endpoint
          const response = await api.post(
            `${getURL('KNOWLEDGE_BASES')}/${kbName}/ingest`,
            formData,
            {
              headers: {
                'Content-Type': 'multipart/form-data',
              },
            }
          );
          ingestResult = response.data;
        } catch (ingestError: any) {
          console.warn('Failed to ingest files:', ingestError);
          // KB was created, but ingestion failed - still show partial success
          setSuccessData({
            title: `Knowledge base "${sourceName}" created, but file ingestion failed. You can add files later.`,
          });
          onSubmit?.({
            sourceName,
            files,
            embeddingModel: selectedEmbeddingModel,
          });
          setOpen(false);
          resetForm();
          return;
        }
      }

      // Build form data for callback
      const callbackData: KnowledgeBaseFormData = {
        sourceName,
        files,
        embeddingModel: selectedEmbeddingModel,
      };

      if (files.length > 0) {
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
    }
    // Reset input so the same file can be selected again
    e.target.value = '';
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles(prev => [...prev, ...Array.from(selectedFiles)]);
    }
    // Reset input so the same folder can be selected again
    e.target.value = '';
  };

  const handleRemoveFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const isFormValid =
    sourceName.trim() !== '' && selectedEmbeddingModel.length > 0;

  return (
    <BaseModal
      size="x-small"
      open={open}
      setOpen={isOpen => {
        setOpen(isOpen);
        if (!isOpen) resetForm();
      }}
      onSubmit={handleSubmit}
    >
      <BaseModal.Trigger asChild>
        {children ? children : <></>}
      </BaseModal.Trigger>

      <BaseModal.Header
        description={
          onOpenExampleFlow ? (
            <span>
              You can optionally add files or folders now, or add them later.
              Try{' '}
              <button
                type="button"
                className="underline"
                onClick={() => {
                  setOpen(false);
                  onOpenExampleFlow();
                }}
              >
                Knowledge Ingestion
              </button>{' '}
              flow for more control.
            </span>
          ) : (
            <span>
              Create a knowledge base to store and search your documents.
            </span>
          )
        }
      >
        <span className="flex items-center gap-2 font-medium">
          <div className="rounded-md bg-muted p-1.5">
            <ForwardedIconComponent name="Database" className="h-5 w-5" />
          </div>
          Add to Knowledge Base
        </span>
      </BaseModal.Header>

      <BaseModal.Content overflowHidden>
        <div className="flex flex-col gap-4 overflow-y-auto px-1">
          {/* Source Name */}
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
            />
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

          {/* Embedding Model Selector */}
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">
              Embedding Model <span className="text-destructive">*</span>
            </Label>

            <ModelInputComponent
              id="kb-embedding-model"
              value={selectedEmbeddingModel}
              editNode={false}
              disabled={false}
              handleOnNewValue={({ value }) => setSelectedEmbeddingModel(value)}
              options={embeddingModelOptions}
              placeholder="Select embedding model"
              showEmptyState
            />
          </div>

          {/* Selected Files */}
          {files.length > 0 && (
            <div className="animate-in fade-in-0 slide-in-from-top-2 duration-300 flex flex-col gap-2 rounded-md border bg-muted/30 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ForwardedIconComponent
                    name="Files"
                    className="h-4 w-4 text-muted-foreground"
                  />
                  <span className="text-sm font-medium">
                    {files.length} file{files.length > 1 ? 's' : ''} selected
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
              <div className="max-h-[120px] overflow-y-auto text-sm text-muted-foreground">
                {files.slice(0, 8).map((file, index) => (
                  <div
                    key={`${file.name}-${index}`}
                    className="animate-in fade-in-0 slide-in-from-left-2 group flex items-center justify-between truncate py-0.5"
                    style={{
                      animationDelay: `${index * 50}ms`,
                      animationFillMode: 'both',
                    }}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <ForwardedIconComponent
                        name={file.webkitRelativePath ? 'File' : 'FileText'}
                        className="h-3 w-3 shrink-0 text-muted-foreground"
                      />
                      <span className="truncate">
                        {file.webkitRelativePath || file.name}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => handleRemoveFile(index)}
                    >
                      <ForwardedIconComponent name="X" className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
                {files.length > 8 && (
                  <div
                    className="animate-in fade-in-0 py-0.5 text-xs"
                    style={{
                      animationDelay: '400ms',
                      animationFillMode: 'both',
                    }}
                  >
                    +{files.length - 8} more files
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </BaseModal.Content>

      <BaseModal.Footer
        submit={{
          label: 'Create',
          disabled: !isFormValid || isSubmitting,
          loading: isSubmitting,
          dataTestId: 'kb-create-button',
        }}
      >
        {onOpenExampleFlow && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" data-testid="kb-browse-btn">
                Add Sources
                <ForwardedIconComponent
                  name="ChevronDown"
                  className="h-4 w-4"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem
                onClick={() => document.getElementById('file-input')?.click()}
              >
                <ForwardedIconComponent
                  name="FileText"
                  className="mr-2 h-4 w-4"
                />
                Upload Files
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => document.getElementById('folder-input')?.click()}
              >
                <ForwardedIconComponent
                  name="Folder"
                  className="mr-2 h-4 w-4"
                />
                Upload Folder
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </BaseModal.Footer>
    </BaseModal>
  );
}
