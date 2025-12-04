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
  usePublishFlow,
  usePublishFlowMarketplaceAdmin,
  useValidateMarketplaceName,
  type PublishCheckResponse,
} from "@/controllers/API/queries/published-flows";
import {
  usePostUploadPresignedUrl,
  useUploadToBlob,
} from "@/controllers/API/queries/flexstore";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { validateFlowForPublish } from "@/utils/flowValidation";
import { incrementPatchVersion } from "@/utils/versionUtils";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { Upload, X, AlertCircle, MessageSquareWarningIcon } from "lucide-react";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { ALLOWED_IMAGE_INPUT_EXTENSIONS } from "@/constants/constants";
import { AgentLogo } from "@/components/AgentLogo";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import type { FlowLatestStatusResponse } from "@/controllers/API/queries/flow-versions";
import { useGetSampleForPublish } from "@/controllers/API/queries/flow-versions";
import { cn } from "@/utils/utils";
import { RiUploadCloud2Fill } from "react-icons/ri";
import useAuthStore from "@/stores/authStore";
import { USER_ROLES } from "@/types/auth";
import { envConfig } from "@/config/env";
import { env } from "process";

interface PublishFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  existingPublishedData?: PublishCheckResponse;
  approvalData?: FlowLatestStatusResponse;
}

export default function PublishFlowModal({
  open,
  setOpen,
  flowId,
  flowName,
  existingPublishedData,
  approvalData,
}: PublishFlowModalProps) {
  const [marketplaceName, setMarketplaceName] = useState(flowName);
  const [version, setVersion] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Debounce marketplace name to avoid excessive API calls while typing
  const debouncedMarketplaceName = useDebouncedValue(marketplaceName, 500);

  // Logo upload state
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const [logoRemoved, setLogoRemoved] = useState(false);
  const [approvedLogoBlobPath, setApprovedLogoBlobPath] = useState<
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
  const [sampleTexts, setSampleTexts] = useState<string[]>([""]); // show one placeholder by default
  // Removed Sample Output state: modal no longer manages sample output here

  // Check if user is Marketplace Admin to use the correct endpoint
  const userRoles = useAuthStore((state) => state.userRoles);
  const isMarketplaceAdmin = userRoles.includes(USER_ROLES.MARKETPLACE_ADMIN);

  // Use appropriate publish hook based on user role
  const { mutate: publishFlowAgent, isPending: isPendingAgent } = usePublishFlow();
  const { mutate: publishFlowMarketplaceAdmin, isPending: isPendingMarketplaceAdmin } = usePublishFlowMarketplaceAdmin();

  // Select the correct hook based on role
  const publishFlow = isMarketplaceAdmin ? publishFlowMarketplaceAdmin : publishFlowAgent;
  const isPending = isMarketplaceAdmin ? isPendingMarketplaceAdmin : isPendingAgent;
  // Ensure `publishedFlowId` is `string | undefined` (coerce possible `null` to `undefined`)
  const publishedFlowId: string | undefined =
    existingPublishedData?.published_flow_id ?? undefined;

  const { mutateAsync: getUploadUrl } = usePostUploadPresignedUrl();
  const { mutateAsync: uploadToBlob } = useUploadToBlob();
  const { mutateAsync: getFlow } = useGetFlow();
  const { validateFileSize } = useFileSizeValidator();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const setCurrentFlowInFlowStore = useFlowStore(
    (state) => state.setCurrentFlow
  );

  // Fetch sample data from version_flow_input_sample for pre-populating the form
  const { data: sampleForPublishData } = useGetSampleForPublish(flowId, version);

  // Derived lists for existing sample files and texts grouped by sample record


  // Sample Output removed: no prefill or tracking here

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

  // Validate marketplace name with debouncing to reduce API calls
  const { data: nameValidation, isLoading: isValidatingName } =
    useValidateMarketplaceName({
      marketplaceName: debouncedMarketplaceName,
      excludeFlowId: flowId, // Exclude current flow when re-publishing
      folderId: currentFlow?.folder_id, // Include folder_id for folder-scoped validation
      enabled: open && debouncedMarketplaceName.trim().length > 0,
    });

  // Pre-fill form fields when modal opens
  useEffect(() => {
    if (open) {
      // Check if flow has been published before (includes both published and unpublished)
      if (existingPublishedData?.marketplace_flow_name) {
        // Previously published: Always use current flow name
        setMarketplaceName(currentFlow?.name || flowName);

        // Use suggested_version from backend if available, otherwise fallback to previous logic
        if (approvalData?.suggested_version) {
          setVersion(approvalData.suggested_version);
        } else if (existingPublishedData.is_published) {
          const newVersion = incrementPatchVersion(
            existingPublishedData.version
          );
          setVersion(newVersion);
        } else {
          // Unpublished: Keep the same version (user can edit)
          setVersion(existingPublishedData.version || "1.0.0");
        }

        setDescription(currentFlow?.description || "");
        setTags(existingPublishedData.tags || []);
        // Clear approved logo since we have published data
        setApprovedLogoBlobPath(null);
      } else {
        // Never published: Default to original flow data
        setMarketplaceName(currentFlow?.name || flowName);
        setDescription(currentFlow?.description || "");

        // Pre-populate tags from approval submission
        if (approvalData?.tags && approvalData.tags.length > 0) {
          setTags(approvalData.tags);
        } else {
          setTags([]);
        }

        // Use suggested_version from backend if available (smart version based on flow_version table)
        if (approvalData?.suggested_version) {
          setVersion(approvalData.suggested_version);
        } else if (approvalData?.latest_version) {
          // Fallback: Keep the approved version (don't auto-increment for first publish)
          setVersion(approvalData.latest_version);
        } else {
          setVersion("1.0.0");
        }

        // Pre-populate logo from approval submission
        if (approvalData?.agent_logo) {
          setApprovedLogoBlobPath(approvalData.agent_logo);
          setLogoUrl(approvalData.agent_logo);
        } else {
          setApprovedLogoBlobPath(null);
          setLogoUrl(null);
        }

        // Note: Sample inputs are now handled by sampleForPublishData useEffect
        // (version_flow_input_sample is the single source of truth)
        setSampleTexts([""]);
        setUploadedSampleFiles([]);
      }
      // Reset logo removal flag and new file state when modal opens
      setLogoRemoved(false);
      setLogoFile(null);
      setLogoPreviewUrl(null);
    }
  }, [
    open,
    existingPublishedData,
    approvalData,
    flowName,
    currentFlow?.name,
    currentFlow?.description,
  ]);

  // Separate useEffect to handle sampleForPublishData loading
  // This ensures sample inputs are set when data becomes available (async)
  // version_flow_input_sample is the single source of truth for sample inputs
  useEffect(() => {
    if (open && sampleForPublishData) {
      console.log("sampleForPublishData loaded, setting sample inputs", sampleForPublishData);

      // Always use sampleForPublishData when available (single source of truth)
      if (sampleForPublishData.sample_text && sampleForPublishData.sample_text.length > 0) {
        console.log("Setting sample texts:", sampleForPublishData.sample_text);
        setSampleTexts(sampleForPublishData.sample_text);
      }

      if (sampleForPublishData.file_names && sampleForPublishData.file_names.length > 0) {
        const sampleFiles = sampleForPublishData.file_names.map((path: string) => ({
          name: path.split("/").pop() || path,
          path: path,
        }));
        console.log("Setting sample files:", sampleFiles);
        setUploadedSampleFiles(sampleFiles);
      }
    }
  }, [open, sampleForPublishData]);

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
    // Validate file type
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

    // Validate file size (5MB limit)
    if (!validateFileSize(file.size)) {
      return; // Error message shown by validator
    }

    setLogoFile(file);
    setLogoRemoved(false);

    // Create preview URL
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
    setLogoRemoved(true);
    setApprovedLogoBlobPath(null);
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

      // Step 1: Get presigned upload URL
      const uploadResponse = await getUploadUrl({
        sourceType: "azureblobstorage",
        fileName: fileName,
        sourceDetails: {
          containerName: envConfig.flexstoreDefaultTemporaryStorageContainer,
          storageAccount: envConfig.flexstoreDefaultTemporaryStorageAccount
        },
      });

      // Step 2: Upload file to Azure blob storage
      await uploadToBlob({
        presignedUrl: uploadResponse.presignedUrl.data.signedUrl,
        file: logoFile,
      });

      // Step 3: Return blob path (not signed URL) to store in database
      // Frontend will generate fresh signed URLs on-demand when displaying the logo
      setLogoUrl(fileName);
      setIsUploadingLogo(false);
      return fileName; // Return blob path like "agent-logos/logo-xxxxx.png"
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

  // Sample images upload handlers
  const uploadSampleFilesToAzure = async (files: File[]): Promise<string[]> => {
    const uploaded: string[] = [];
    try {
      setIsUploadingSamples(true);

      for (const file of files) {
        // Validate size only; allow any file type (PDF, DOCX, etc.)
        if (!validateFileSize(file.size)) {
          continue; // Error shown by validator
        }

        const fileName = `marketplace-samples/${flowId}/${file.name}`;

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

  const handlePublish = async () => {
    // Validate required fields
    if (!marketplaceName.trim()) {
      setErrorData({
        title: "Cannot publish flow",
        list: ["Marketplace flow name is required"],
      });
      return;
    }

    // Validate version is required
    if (!version || !version.trim()) {
      setErrorData({
        title: "Cannot publish flow",
        list: ["Version is required"],
      });
      return;
    }

    // Check if name is available
    if (nameValidation && !nameValidation.available) {
      setErrorData({
        title: "Cannot publish flow",
        list: [
          nameValidation.message || "This marketplace name is already taken",
        ],
      });
      return;
    }

    // Validate flow before publishing
    if (!currentFlow) {
      setErrorData({
        title: "Cannot publish flow",
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
        title: "Cannot Publish Flow",
        list: errors,
      });
      return;
    }

    // Validation passed - clear any previous errors and proceed with publish
    setValidationErrors([]);

    // Sample Output removed: no parsing or patching on publish

    // Upload logo if a new one was selected
    let finalLogoUrl = logoRemoved
      ? null
      : logoUrl || existingPublishedData?.flow_icon || null;
    if (logoFile && !logoUrl && !logoRemoved) {
      const uploadedLogoUrl = await uploadLogoToAzure();
      if (uploadedLogoUrl) {
        finalLogoUrl = uploadedLogoUrl;
      } else {
        // Logo upload failed, but we can still publish without it
        // Error was already shown by uploadLogoToAzure
        finalLogoUrl = null;
      }
    }

    publishFlow(
      {
        flowId,
        payload: {
          marketplace_flow_name: marketplaceName,
          version: version || undefined,
          description: description || undefined,
          tags: tags.length > 0 ? tags : undefined,
          flow_icon: finalLogoUrl || undefined,
          // Sample input payload
          storage_account: DEFAULT_STORAGE_ACCOUNT,
          container_name: DEFAULT_CONTAINER_NAME,
          file_names: uploadedSampleFiles.length
            ? uploadedSampleFiles.map((f) => f.path)
            : undefined,
          sample_text: sampleTexts.filter((t) => t.trim().length > 0),
          // sample_output removed from publish payload
        },
      },
      {
        onSuccess: async () => {
          setSuccessData({
            title: "Flow published successfully!",
          });

          // Refetch the updated flow to get the new marketplace name
          try {
            const updatedFlow = await getFlow({ id: flowId });
            if (updatedFlow) {
              setCurrentFlow(updatedFlow); // Update flowsManagerStore
              setCurrentFlowInFlowStore(updatedFlow); // Update flowStore
            }
          } catch (error) {
            console.error("Failed to refetch flow after publish:", error);
            // Don't show error to user - publish succeeded, this is just a UI update
          }

          setOpen(false);
          // Reset form
          setMarketplaceName("");
          setVersion("");
          setDescription("");
          setTags([]);
          handleRemoveLogo();
          setUploadedSampleFiles([]);
          setSampleTexts([]);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to publish flow",
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
      <DialogContent className="sm:max-w-[900px] max-h-[95vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Publish the Agent to MarketPlace</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 my-6 overflow-y-auto pr-2 max-h-[calc(100vh-192px)] ">
          <div className="space-y-2">
            <Label htmlFor="marketplace-name">
              Name <span className="text-error">*</span>
            </Label>
            <div className="relative">
              <Input
                id="marketplace-name"
                placeholder={flowName}
                value={marketplaceName}
                onChange={(e) => setMarketplaceName(e.target.value)}
                required
                className={
                  nameValidation && !nameValidation.available
                    ? "border-error focus-visible:ring-error"
                    : ""
                }
              />
              {(isValidatingName ||
                marketplaceName !== debouncedMarketplaceName) &&
                marketplaceName.trim().length > 0 && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  </div>
                )}
            </div>
            <div className="h-4">
              {nameValidation && !nameValidation.available && (
                <div className="flex items-start gap-2 text-sm text-error">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{nameValidation.message}</span>
                </div>
              )}
              {nameValidation &&
                nameValidation.available &&
                marketplaceName.trim().length > 0 && (
                  <p className="text-sm text-green-600 dark:text-green-500">
                    ✓ This name is available
                  </p>
                )}
            </div>
            <p className="text-xs text-muted-foreground">
              Name for workflow in the marketplace
            </p>
          </div>

          <div className="flex gap-4">
            <div className="space-y-2 flex-[2]">
              <Label htmlFor="version">
                Version <span className="text-error">*</span>
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

            <div className="space-y-2 flex-[3]">
              <Label htmlFor="tags">Tags (Optional)</Label>
              <MultiSelect
                options={MARKETPLACE_TAGS}
                selected={tags}
                onChange={setTags}
                placeholder="Select tags..."
              />
              <p className="text-xs text-muted-foreground">
                Select one or more tags to categorize your flow
              </p>
            </div>
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
            <p className="text-xs text-secondary-font">
              Describe what this agent does and how to use it
            </p>
          </div>

          {/* Agent Logo Upload Section */}
          <div className="space-y-2">
            <Label htmlFor="agent-logo">Agent Logo (Optional)</Label>
            <div className="flex gap-4 items-start">
              {/* Logo Preview */}
              {!logoRemoved &&
                (logoPreviewUrl ||
                  existingPublishedData?.flow_icon ||
                  approvedLogoBlobPath) && (
                  <div className="flex h-[60px] w-[70px] items-center justify-center rounded-lg border relative">
                    {logoPreviewUrl ? (
                      // Local file preview (before upload)
                      <img
                        src={logoPreviewUrl}
                        alt="Agent logo preview"
                        className="h-full w-full object-contain rounded-lg p-1"
                      />
                    ) : (
                      // Existing logo (from published data or approved submission) - generate signed URL
                      <div className="h-full w-full">
                        <AgentLogo
                          blobPath={
                            existingPublishedData?.flow_icon ||
                            approvedLogoBlobPath ||
                            null
                          }
                          updatedAt={
                            existingPublishedData?.flow_icon_updated_at || null
                          }
                          altText="Agent logo preview"
                          className="h-full w-full"
                        />
                      </div>
                    )}
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
              {(logoRemoved ||
                (!logoPreviewUrl && !existingPublishedData?.flow_icon)) && (
                  <div
                    className={`flex flex-col py-10 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-primary-border hover:border-secondary-border border-dashed p-8 transition-colors `}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                  >
                    {/* <Upload className="h-5 w-5 text-muted-foreground" /> */}
                    <RiUploadCloud2Fill className="h-14 w-14 text-secondary-font opacity-70" />
                    <p className="text-center">
                      <span className="text-[13px] font-medium text-secondary-font block">
                        {isDragging
                          ? "Drop logo here"
                          : "Drag and drop or click to upload"}
                      </span>
                      <span className="text-[10px] text-secondary-font italic opacity-70 block">
                        Supported formats:{" "}
                        {ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ").toUpperCase()}
                      </span>
                    </p>
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
              displayed in the marketplace.
            </p> */}
          </div>

          {/* Sample Inputs Section */}
          {(hasFilePathInput || hasTextOrChatInput) && (
            <div className="space-y-1">
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
                      <button
                        type="button"
                        className="text-sm text-primary hover:underline"
                        onClick={() => sampleFilesInputRef.current?.click()}
                        disabled={isUploadingSamples}
                      ></button>
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
                            <X className="h-4 w-4 !text-error" />
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
                    <span className="text-sm text-secondary-font">
                      Sample Input Text
                    </span>
                    <button
                      type="button"
                      className="text-sm text-menu hover:underline"
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
                            <X className="h-4 w-4 text-error" />
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
            <div className="rounded-lg bg-accent-light p-4 text-sm space-y-2">
              <p className="font-medium text-primary-font">
                What happens when you publish?
              </p>
              <ul className="list-disc list-inside space-y-1 text-secondary-font">
                <li>
                  Your flow will be visible to all users in the Marketplace
                </li>
                <li>To update the marketplace, you'll need to re-publish</li>
              </ul>
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="rounded-md bg-error-bg p-4 border border-error">
              <h4 className="flex items-center gap-2 text-sm font-medium text-error mb-2">
                <MessageSquareWarningIcon />
                <span>Cannot Publish - Please Fix These Issues:</span>
              </h4>
              <ul className="list-disc list-inside space-y-1">
                {validationErrors.map((error, index) => (
                  <li key={index} className="text-sm text-error">
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
            onClick={handlePublish}
            disabled={
              isPending ||
              isUploadingLogo ||
              isUploadingSamples ||
              validationErrors.length > 0 ||
              isValidatingName ||
              (nameValidation && !nameValidation.available)
            }
          >
            {isUploadingLogo
              ? "Uploading Logo..."
              : isUploadingSamples
                ? "Uploading Samples..."
                : isPending
                  ? "Publishing..."
                  : "Publish to Marketplace"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
