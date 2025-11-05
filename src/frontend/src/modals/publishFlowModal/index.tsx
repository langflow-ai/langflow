import { useState, useEffect, useRef } from "react";
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
  useValidateMarketplaceName,
  type PublishCheckResponse,
} from "@/controllers/API/queries/published-flows";
import {
  usePostUploadPresignedUrl,
  useUploadToBlob,
} from "@/controllers/API/queries/flexstore";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { validateFlowForPublish } from "@/utils/flowValidation";
import { incrementPatchVersion } from "@/utils/versionUtils";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { Upload, X, AlertCircle } from "lucide-react";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { ALLOWED_IMAGE_INPUT_EXTENSIONS } from "@/constants/constants";
import { AgentLogo } from "@/components/AgentLogo";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

interface PublishFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  existingPublishedData?: PublishCheckResponse;
}

export default function PublishFlowModal({
  open,
  setOpen,
  flowId,
  flowName,
  existingPublishedData,
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { mutate: publishFlow, isPending } = usePublishFlow();
  const { mutateAsync: getUploadUrl } = usePostUploadPresignedUrl();
  const { mutateAsync: uploadToBlob } = useUploadToBlob();
  const { validateFileSize } = useFileSizeValidator();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  // Validate marketplace name with debouncing to reduce API calls
  const {
    data: nameValidation,
    isLoading: isValidatingName,
  } = useValidateMarketplaceName({
    marketplaceName: debouncedMarketplaceName,
    excludeFlowId: flowId, // Exclude current flow when re-publishing
    enabled: open && debouncedMarketplaceName.trim().length > 0,
  });

  // Pre-fill form fields when modal opens
  useEffect(() => {
    if (open) {
      // Check if flow has been published before (includes both published and unpublished)
      if (existingPublishedData?.marketplace_flow_name) {
        // Previously published: Always use current flow name
        setMarketplaceName(flowName);

        // Auto-increment version only if currently published, otherwise keep same version
        if (existingPublishedData.is_published) {
          const newVersion = incrementPatchVersion(existingPublishedData.version);
          setVersion(newVersion);
        } else {
          // Unpublished: Keep the same version (user can edit)
          setVersion(existingPublishedData.version || "1.0.0");
        }

        setDescription(existingPublishedData.description || "");
        setTags(existingPublishedData.tags || []);
      } else {
        // Never published: Default to original flow data
        setMarketplaceName(flowName);
        setVersion("1.0.0");
        setDescription("");
        setTags([]);
      }
      // Reset logo removal flag when modal opens
      setLogoRemoved(false);
    }
  }, [open, existingPublishedData, flowName]);

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
    if (!fileExtension || !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)) {
      setErrorData({
        title: "Invalid File Type",
        list: [
          `Please upload an image file (${ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ")})`,
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
          containerName: "ai-studio-v2",
          storageAccount: "autonomizestorageaccount",
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
        list: [nameValidation.message || "This marketplace name is already taken"],
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

    // Upload logo if a new one was selected
    let finalLogoUrl = logoRemoved ? null : (logoUrl || existingPublishedData?.flow_icon || null);
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
        },
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: "Flow published successfully!",
          });
          setOpen(false);
          // Reset form
          setMarketplaceName("");
          setVersion("");
          setDescription("");
          setTags([]);
          handleRemoveLogo();
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
      <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Publish the Agent to MarketPlace</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4 overflow-y-auto pr-2">
          <div className="space-y-2">
            <Label htmlFor="marketplace-name">
              Marketplace Flow Name <span className="text-destructive">*</span>
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
                    ? "border-destructive focus-visible:ring-destructive"
                    : ""
                }
              />
              {(isValidatingName || marketplaceName !== debouncedMarketplaceName) && marketplaceName.trim().length > 0 && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              )}
            </div>
            <div className="h-4">
              {nameValidation && !nameValidation.available && (
                <div className="flex items-start gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{nameValidation.message}</span>
                </div>
              )}
              {nameValidation && nameValidation.available && marketplaceName.trim().length > 0 && (
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
                Version <span className="text-destructive">*</span>
              </Label>
              <Input
                id="version"
                placeholder="1.0.0"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                Semantic versioning recommended (e.g., 1.0.0, 1.2.3)
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
            <p className="text-xs text-muted-foreground">
              Describe what this agent does and how to use it
            </p>
          </div>

          {/* Agent Logo Upload Section */}
          <div className="space-y-2">
            <Label htmlFor="agent-logo">Agent Logo (Optional)</Label>
            <div className="flex gap-4 items-start">
              {/* Logo Preview */}
              {!logoRemoved && (logoPreviewUrl || existingPublishedData?.flow_icon) && (
                <div className="relative h-24 w-24 rounded-lg border bg-muted flex-shrink-0">
                  {logoPreviewUrl ? (
                    // Local file preview (before upload)
                    <img
                      src={logoPreviewUrl}
                      alt="Agent logo preview"
                      className="h-full w-full object-contain rounded-lg p-1"
                    />
                  ) : (
                    // Existing published logo (blob path) - generate signed URL
                    <div className="h-full w-full">
                      <AgentLogo
                        blobPath={existingPublishedData?.flow_icon || null}
                        updatedAt={existingPublishedData?.flow_icon_updated_at || null}
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
              {(logoRemoved || (!logoPreviewUrl && !existingPublishedData?.flow_icon)) && (
                <div
                  className={`flex h-24 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed transition-colors ${
                    isDragging
                      ? "border-primary bg-primary/10"
                      : "border-muted-foreground/25 hover:border-primary hover:bg-muted"
                  }`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <Upload className="h-5 w-5 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {isDragging ? "Drop logo here" : "Drag and drop or click to upload"}
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
            <p className="text-xs text-muted-foreground">
              Upload a logo for your agent (PNG, JPG, JPEG). This will be displayed in the marketplace.
            </p>
          </div>

          {validationErrors.length === 0 && (
            <div className="rounded-lg bg-muted p-4 text-sm space-y-2">
              <p className="font-medium">What happens when you publish?</p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Your flow will be visible to all users in the Marketplace</li>
                <li>To update the marketplace, you'll need to re-publish</li>
              </ul>
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="rounded-md bg-red-50 p-4 border border-red-200">
              <h4 className="text-sm font-semibold text-red-800 mb-2">
                ⚠️ Cannot Publish - Please Fix These Issues:
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
            onClick={handlePublish}
            disabled={
              isPending ||
              isUploadingLogo ||
              validationErrors.length > 0 ||
              isValidatingName ||
              (nameValidation && !nameValidation.available)
            }
          >
            {isUploadingLogo
              ? "Uploading Logo..."
              : isPending
              ? "Publishing..."
              : "Publish to Marketplace"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
