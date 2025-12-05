import { useState, useEffect, useRef, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MultiSelect } from "@/components/ui/multi-select";
import {
  useSubmitFlowForApproval,
  useGetFlowLatestStatus,
} from "@/controllers/API/queries/flow-versions";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useValidateMarketplaceName } from "@/controllers/API/queries/published-flows/use-validate-marketplace-name";
import { incrementPatchVersion } from "@/utils/versionUtils";
import {
  usePostUploadPresignedUrl,
  useUploadToBlob,
} from "@/controllers/API/queries/flexstore";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { validateFlowForPublish } from "@/utils/flowValidation";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { AlertCircle, X } from "lucide-react";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { ALLOWED_IMAGE_INPUT_EXTENSIONS } from "@/constants/constants";
import { AgentLogo } from "@/components/AgentLogo";
import { RiUploadCloud2Fill } from "react-icons/ri";
import { envConfig } from "@/config/env";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

interface SubmitForApprovalModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
}

export default function SubmitForApprovalModal({
  open,
  setOpen,
  flowId,
  flowName,
}: SubmitForApprovalModalProps) {
  const [title, setTitle] = useState(flowName);
  const [version, setVersion] = useState("1.0.0");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Logo upload state
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const [existingLogoBlobPath, setExistingLogoBlobPath] = useState<
    string | null
  >(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sample input state
  const DEFAULT_STORAGE_ACCOUNT = envConfig.flexstoreDefaultTemporaryStorageAccount;
  const DEFAULT_CONTAINER_NAME = envConfig.flexstoreDefaultTemporaryStorageContainer;
  const [isUploadingSamples, setIsUploadingSamples] = useState(false);
  const [uploadedSampleFiles, setUploadedSampleFiles] = useState<
    { name: string; path: string }[]
  >([]);
  const sampleFilesInputRef = useRef<HTMLInputElement>(null);
  const [sampleTexts, setSampleTexts] = useState<string[]>([""]);

  // Debounced title for name validation
  const debouncedTitle = useDebouncedValue(title, 500);

  const { mutate: submitFlow, isPending } = useSubmitFlowForApproval();
  const { data: latestStatus } = useGetFlowLatestStatus(flowId);
  const { mutateAsync: getUploadUrl } = usePostUploadPresignedUrl();
  const { mutateAsync: uploadToBlob } = useUploadToBlob();
  const { validateFileSize } = useFileSizeValidator();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const { mutateAsync: getFlow } = useGetFlow();

  // Name validation hook - validates against marketplace
  const { data: nameValidation, isLoading: isValidatingName } =
    useValidateMarketplaceName({
      marketplaceName: debouncedTitle,
      excludeFlowId: flowId,
      folderId: currentFlow?.folder_id,
      enabled: open && debouncedTitle.trim().length > 0,
    });

  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const setCurrentFlowInFlowStore = useFlowStore(
    (state) => state.setCurrentFlow
  );

  // Detect presence of inputs in the current flow to conditionally render sections
  const hasTextOrChatInput = useMemo(() => {
    const nodes = (currentFlow?.data?.nodes ?? []) as AllNodeType[];
    return nodes.some((node) => {
      const type = node.data?.type;
      return type === "ChatInput" || type === "TextInput";
    });
  }, [currentFlow]);

  const hasFilePathInput = useMemo(() => {
    const nodes = (currentFlow?.data?.nodes ?? []) as AllNodeType[];
    return nodes.some((node) => node.data?.type === "FilePathInput");
  }, [currentFlow]);

  // Pre-fill form fields when modal opens
  useEffect(() => {
    if (open) {
      setTitle(currentFlow?.name || flowName);
      // Auto-increment version from this flow's latest version
      const nextVersion = latestStatus?.latest_version
        ? incrementPatchVersion(latestStatus.latest_version)
        : "1.0.0";
      setVersion(nextVersion);
      setDescription(currentFlow?.description || "");
      setLogoFile(null);
      setLogoPreviewUrl(null);

      // Pre-populate tags from previous submission
      if (latestStatus?.tags && latestStatus.tags.length > 0) {
        setTags(latestStatus.tags);
      } else {
        setTags([]);
      }

      // Pre-populate logo from previous submission
      if (latestStatus?.agent_logo) {
        setExistingLogoBlobPath(latestStatus.agent_logo);
        setLogoUrl(latestStatus.agent_logo);
      } else {
        setExistingLogoBlobPath(null);
        setLogoUrl(null);
      }

      // Pre-populate sample inputs from previous submission (for re-submissions)
      if (latestStatus?.sample_text && latestStatus.sample_text.length > 0) {
        setSampleTexts(latestStatus.sample_text);
      } else {
        setSampleTexts([""]);
      }

      if (latestStatus?.file_names && latestStatus.file_names.length > 0) {
        setUploadedSampleFiles(
          latestStatus.file_names.map((path) => ({
            name: path.split("/").pop() || path,
            path: path,
          }))
        );
      } else {
        setUploadedSampleFiles([]);
      }
    }
  }, [
    open,
    flowName,
    currentFlow?.name,
    currentFlow?.description,
    latestStatus,
  ]);

  // Run validation when modal opens
  useEffect(() => {
    if (open && currentFlow) {
      const nodes = (currentFlow.data?.nodes ?? []) as AllNodeType[];
      const edges = (currentFlow.data?.edges ?? []) as EdgeType[];
      const errors = validateFlowForPublish(nodes, edges);
      setValidationErrors(errors);
    }
  }, [open, currentFlow]);

  // Logo upload handlers
  const handleFileSelect = (file: File) => {
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    if (
      !fileExtension ||
      !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
    ) {
      setErrorData({
        title: "Invalid File Type",
        list: [
          `Please upload an image file (${ALLOWED_IMAGE_INPUT_EXTENSIONS.join(
            ", "
          )})`,
        ],
      });
      return;
    }

    if (!validateFileSize(file.size)) {
      return;
    }

    setLogoFile(file);

    const reader = new FileReader();
    reader.onloadend = () => {
      setLogoPreviewUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleRemoveLogo = () => {
    setLogoFile(null);
    setLogoPreviewUrl(null);
    setLogoUrl(null);
    setExistingLogoBlobPath(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const uploadLogoToAzure = async (): Promise<string | null> => {
    if (!logoFile) return null;

    try {
      setIsUploadingLogo(true);

      const fileExtension = logoFile.name.split(".").pop();
      const fileName = `agent-logos/logo-${flowId}-${Date.now()}.${fileExtension}`;

      const uploadResponse = await getUploadUrl({
        sourceType: "azureblobstorage",
        fileName: fileName,
        sourceDetails: {
          containerName: envConfig.flexstoreDefaultTemporaryStorageContainer,
          storageAccount: envConfig.flexstoreDefaultTemporaryStorageAccount
        },
      });

      await uploadToBlob({
        presignedUrl: uploadResponse.presignedUrl.data.signedUrl,
        file: logoFile,
      });

      setLogoUrl(fileName);
      setIsUploadingLogo(false);
      return fileName;
    } catch (error: any) {
      console.error("Logo upload error:", error);
      setIsUploadingLogo(false);
      setErrorData({
        title: "Logo Upload Failed",
        list: [error.message || "Failed to upload logo to storage"],
      });
      return null;
    }
  };

  // Sample files upload handlers
  const uploadSampleFilesToAzure = async (files: File[]): Promise<string[]> => {
    const uploaded: string[] = [];
    try {
      setIsUploadingSamples(true);

      for (const file of files) {
        if (!validateFileSize(file.size)) {
          continue;
        }

        const fileName = `approval-samples/${flowId}/${file.name}`;

        const uploadResponse = await getUploadUrl({
          sourceType: "azureblobstorage",
          fileName,
          sourceDetails: {
            containerName: DEFAULT_CONTAINER_NAME,
            storageAccount: DEFAULT_STORAGE_ACCOUNT,
          },
        });

        await uploadToBlob({
          presignedUrl: uploadResponse.presignedUrl.data.signedUrl,
          file,
        });

        uploaded.push(fileName);
        setUploadedSampleFiles((prev) => [
          ...prev,
          { name: file.name, path: fileName },
        ]);
      }
    } catch (error: any) {
      console.error("Sample upload error:", error);
      setErrorData({
        title: "Sample Upload Failed",
        list: [error?.message || "Failed to upload sample files"],
      });
    } finally {
      setIsUploadingSamples(false);
    }
    return uploaded;
  };

  const handleSampleFilesSelect = async (filesList: FileList | null) => {
    if (!filesList || filesList.length === 0) return;
    const files = Array.from(filesList);
    await uploadSampleFilesToAzure(files);
    if (sampleFilesInputRef.current) {
      sampleFilesInputRef.current.value = "";
    }
  };

  const removeSampleFile = (index: number) => {
    setUploadedSampleFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Sample text handlers
  const addSampleText = () => setSampleTexts((prev) => [...prev, ""]);
  const updateSampleText = (index: number, value: string) =>
    setSampleTexts((prev) => prev.map((t, i) => (i === index ? value : t)));
  const removeSampleText = (index: number) =>
    setSampleTexts((prev) => prev.filter((_, i) => i !== index));

  const handleSubmit = async () => {
    // Validate required fields
    if (!title.trim()) {
      setErrorData({
        title: "Cannot submit flow",
        list: ["Title is required"],
      });
      return;
    }

    if (!version.trim()) {
      setErrorData({
        title: "Cannot submit flow",
        list: ["Version is required"],
      });
      return;
    }

    // Validate flow before submitting
    if (!currentFlow) {
      setErrorData({
        title: "Cannot submit flow",
        list: ["Flow data not available"],
      });
      return;
    }

    const nodes = (currentFlow.data?.nodes ?? []) as AllNodeType[];
    const edges = (currentFlow.data?.edges ?? []) as EdgeType[];
    const errors = validateFlowForPublish(nodes, edges);

    if (errors.length > 0) {
      setValidationErrors(errors);
      setErrorData({
        title: "Cannot Submit Flow",
        list: errors,
      });
      return;
    }

    setValidationErrors([]);

    // Upload logo if a new one was selected
    let finalLogoUrl = logoUrl || null;
    if (logoFile && !logoUrl) {
      const uploadedLogoUrl = await uploadLogoToAzure();
      if (uploadedLogoUrl) {
        finalLogoUrl = uploadedLogoUrl;
      }
    }

    submitFlow(
      {
        flowId,
        payload: {
          title,
          version,
          description: description || undefined,
          tags: tags.length > 0 ? tags : undefined,
          agent_logo: finalLogoUrl || undefined,
          storage_account: DEFAULT_STORAGE_ACCOUNT,
          container_name: DEFAULT_CONTAINER_NAME,
          file_names: uploadedSampleFiles.length
            ? uploadedSampleFiles.map((f) => f.path)
            : undefined,
          sample_text: sampleTexts.filter((t) => t.trim().length > 0),
        },
      },
      {
        onSuccess: async () => {
          setSuccessData({
            title: "Flow submitted for approval!",
          });

          // Refetch the updated flow to get the new title/description
          try {
            const updatedFlow = await getFlow({ id: flowId });
            if (updatedFlow) {
              setCurrentFlow(updatedFlow); // Update flowsManagerStore
              setCurrentFlowInFlowStore(updatedFlow); // Update flowStore
            }
          } catch (error) {
            console.error("Failed to refetch flow after submit:", error);
          }

          setOpen(false);
          // Reset form
          setTitle("");
          setVersion("1.0.0");
          setDescription("");
          setTags([]);
          handleRemoveLogo();
          setUploadedSampleFiles([]);
          setSampleTexts([""]);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to submit flow",
            list: [
              error?.response?.data?.detail || error.message || "Unknown error",
            ],
          });
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Submit Agent for Approval</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 my-4 overflow-y-auto pr-2 max-h-[calc(90vh-130px)]">
          <div className="space-y-2">
            <Label htmlFor="title">
              Title <span className="text-destructive">*</span>
            </Label>
            <Input
              id="title"
              placeholder={flowName}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <p className="text-xs text-muted-foreground">
              Title for the agent submission
            </p>
            {nameValidation && !nameValidation.available && (
              <div className="flex items-start gap-2 text-sm text-error">
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>{nameValidation.message}</span>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="version">
              Version <span className="text-destructive">*</span>
            </Label>
            <Input
              id="version"
              placeholder="1.0.0"
              value={version}
              readOnly
              className="bg-muted cursor-not-allowed"
            />
            <p className="text-xs text-muted-foreground">
              Auto-generated version (e.g., 1.0.0, 1.0.1)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tags">Tags (Optional)</Label>
            <MultiSelect
              options={MARKETPLACE_TAGS}
              selected={tags}
              onChange={setTags}
              placeholder="Select tags..."
            />
            <p className="text-xs text-muted-foreground">
              Select one or more tags to categorize your agent
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (Optional)</Label>
            <Textarea
              id="description"
              placeholder="Describe what this agent does and how to use it"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
            />
            <p className="text-xs text-muted-foreground">
              Describe what this agent does and how to use it
            </p>
          </div>

          {/* Agent Logo Upload Section */}
          <div className="space-y-2">
            <Label htmlFor="agent-logo">Agent Logo (Optional)</Label>
            <div className="flex gap-4 items-start">
              {/* New Logo Preview (from file upload) */}
              {logoPreviewUrl && (
                <div className="relative h-24 w-24 rounded-lg border bg-muted flex-shrink-0">
                  <img
                    src={logoPreviewUrl}
                    alt="Agent logo preview"
                    className="h-full w-full object-contain rounded-lg p-1"
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90 p-0"
                    onClick={handleRemoveLogo}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {/* Existing Logo Preview (from previous submission) */}
              {!logoPreviewUrl && existingLogoBlobPath && (
                <div className="relative h-24 w-24 rounded-lg border bg-muted flex-shrink-0">
                  <AgentLogo
                    blobPath={existingLogoBlobPath}
                    altText="Previous agent logo"
                    className="h-full w-full"
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90 p-0"
                    onClick={handleRemoveLogo}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {/* Upload Dropzone */}
              {!logoPreviewUrl && !existingLogoBlobPath && (
                <div
                  className={`flex flex-col py-5 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-primary-border hover:border-secondary-border border-dashed p-8 transition-colors `}
                  // className={`flex h-24 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed transition-colors ${
                  //   isDragging
                  //     ? "border-primary bg-primary/10"
                  //     : "border-muted-foreground/25 hover:border-primary hover:bg-muted"
                  // }
                  // `}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {/* <Upload className="h-5 w-5 text-muted-foreground" /> */}
                  <RiUploadCloud2Fill className="h-14 w-14 text-secondary-font opacity-70" />
                  <span className="text-[13px] font-medium text-secondary-font block">
                    {isDragging
                      ? "Drop logo here"
                      : "Drag and drop or click to upload"}
                  </span>
                  <span className="text-[10px] text-secondary-font italic opacity-70 block">
                    Supported formats:{" "}
                    {ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ").toUpperCase()}
                  </span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    hidden
                    accept={ALLOWED_IMAGE_INPUT_EXTENSIONS.join(",")}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(file);
                    }}
                  />
                </div>
              )}
            </div>
            {/* <p className="text-xs text-muted-foreground">
              Upload a logo for your agent (PNG, JPG, JPEG). This will be
              displayed during review.
            </p> */}
          </div>

          {/* Sample Inputs Section */}
          {(hasFilePathInput || hasTextOrChatInput) && (
            <div className="space-y-4">
              <Label>Sample Inputs (Optional)</Label>
              {/* Sample Input Files */}
              {hasFilePathInput && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Sample Input files
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => sampleFilesInputRef.current?.click()}
                        disabled={isUploadingSamples}
                      >
                        {isUploadingSamples ? "Uploading..." : "Add File"}
                      </Button>
                    </div>
                    <input
                      ref={sampleFilesInputRef}
                      type="file"
                      hidden
                      multiple
                      onChange={(e) => handleSampleFilesSelect(e.target.files)}
                    />
                  </div>
                  {uploadedSampleFiles.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {uploadedSampleFiles.map((f, idx) => (
                        <div
                          key={`${f.path}-${idx}`}
                          className="flex items-center gap-2 bg-muted px-2 py-1 rounded"
                        >
                          <span className="text-xs">{f.name}</span>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={() => removeSampleFile(idx)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Sample Input Text */}
              {hasTextOrChatInput && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Sample Input Text
                    </span>
                    <button
                      type="button"
                      className="text-sm text-primary hover:underline"
                      onClick={addSampleText}
                    >
                      + Add More
                    </button>
                  </div>
                  {sampleTexts.length > 0 && (
                    <div className="space-y-3">
                      {sampleTexts.map((text, idx) => (
                        <div
                          key={`sample-text-${idx}`}
                          className="flex items-center gap-2"
                        >
                          <Input
                            value={text}
                            onChange={(e) =>
                              updateSampleText(idx, e.target.value)
                            }
                            placeholder="Enter Sample Input Text"
                          />
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => removeSampleText(idx)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {validationErrors.length === 0 && (
            <div className="rounded-lg bg-muted p-4 text-sm space-y-2">
              <p className="font-medium">
                What happens when you submit for approval?
              </p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Your flow will be sent to an admin for review</li>
                <li>
                  You will not be able to edit the flow while it is under review
                </li>
                <li>Once approved, you can publish it to the marketplace</li>
              </ul>
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="rounded-md bg-red-50 p-4 border border-red-200">
              <h4 className="text-sm font-semibold text-red-800 mb-2">
                Cannot Submit - Please Fix These Issues:
              </h4>
              <ul className="list-disc list-inside space-y-1">
                {validationErrors.map((error, index) => (
                  <li key={index} className="text-sm text-red-700">
                    {error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isPending || isUploadingLogo}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={
              isPending ||
              isUploadingLogo ||
              isUploadingSamples ||
              isValidatingName ||
              (nameValidation && !nameValidation.available) ||
              validationErrors.length > 0
            }
          >
            {isUploadingLogo
              ? "Uploading Logo..."
              : isUploadingSamples
              ? "Uploading Samples..."
              : isPending
              ? "Submitting..."
              : "Submit for Approval"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
