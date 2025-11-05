import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import useLogoStore from "@/stores/logoStore";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { ALLOWED_IMAGE_INPUT_EXTENSIONS } from "@/constants/constants";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  usePostUploadPresignedUrl,
  useUploadToBlob,
} from "@/controllers/API/queries/flexstore";
import { useUpdateAppConfig } from "@/controllers/API/queries/application-config";
import useAlertStore from "@/stores/alertStore";
import { AppLogoDisplay } from "@/components/AppLogoDisplay";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";

const LogoUploadForm = () => {
  const { logoUrl, setLogoUrl } = useLogoStore();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isLogoRemoved, setIsLogoRemoved] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { validateFileSize } = useFileSizeValidator();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { queryClient } = UseRequestProcessor();

  const { mutateAsync: getUploadUrl } = usePostUploadPresignedUrl();
  const { mutateAsync: uploadToBlob } = useUploadToBlob();
  const { mutateAsync: updateAppConfig } = useUpdateAppConfig();

  const handleFileSelect = (file: File) => {
    // Validate file type
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    if (!fileExtension || !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)) {
      setErrorData({
        title: "Invalid File Type",
        list: [`Please upload an image file (${ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ")})`],
      });
      return;
    }

    // Validate file size
    try {
      validateFileSize(file);
    } catch (error: any) {
      setErrorData({
        title: "File Size Error",
        list: [error.message || "File size exceeds the maximum allowed size"],
      });
      return;
    }

    // Store the file for upload
    setSelectedFile(file);
    setIsLogoRemoved(false);

    // Convert to base64 data URL for local preview only (not uploaded yet)
    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      setPreviewUrl(result);
    };
    reader.readAsDataURL(file);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleRemoveLogo = () => {
    setIsLogoRemoved(true);
    setPreviewUrl(null);
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSaveLogo = async () => {
    // If user removed the logo, delete it from database
    if (isLogoRemoved && !selectedFile) {
      setIsUploading(true);
      try {
        await updateAppConfig({
          key: "app-logo",
          value: "",
          description: "Application logo removed",
        });
        setLogoUrl(null);

        // Invalidate the GET query cache so all users get the updated logo state
        queryClient.invalidateQueries({ queryKey: ["useGetAppConfig", "app-logo"] });

        setSuccessData({
          title: "Logo Removed Successfully",
        });
        setIsLogoRemoved(false);
      } catch (error: any) {
        setErrorData({
          title: "Failed to Remove Logo",
          list: [error.message || "Please try again."],
        });
      } finally {
        setIsUploading(false);
      }
      return;
    }

    if (!selectedFile) {
      setErrorData({
        title: "No File Selected",
        list: ["Please select a logo file before saving"],
      });
      return;
    }

    setIsUploading(true);

    try {
      const fileExtension = selectedFile.name.split(".").pop();
      const fileName = `app-logo/logo-${Date.now()}.${fileExtension}`;

      // Step 1: Get presigned upload URL from BFF
      const uploadResponse = await getUploadUrl({
        sourceType: "azureblobstorage",
        fileName: fileName,
        sourceDetails: {
          containerName: "ai-studio-v2",
          storageAccount: "autonomizestorageaccount",
        },
      });

      // Step 2: Upload file directly to Azure blob storage
      await uploadToBlob({
        presignedUrl: uploadResponse.presignedUrl.data.signedUrl,
        file: selectedFile,
      });

      // Step 3: Save ONLY the blob path to database (not signed URL)
      // Frontend will generate fresh signed URLs on-demand when displaying the logo
      await updateAppConfig({
        key: "app-logo",
        value: fileName,  // Store blob path like "app-logo/logo-xxxxx.png"
        description: "Application logo blob path",
      });

      // Step 4: Save the blob path to logoStore (will be converted to signed URL on display)
      setLogoUrl(fileName);

      // Invalidate the GET query cache so all users get the updated logo state
      queryClient.invalidateQueries({ queryKey: ["useGetAppConfig", "app-logo"] });

      setSuccessData({
        title: "Logo Uploaded Successfully",
      });

      // Clear the local preview and selected file after successful upload
      setPreviewUrl(null);
      setSelectedFile(null);
    } catch (error: any) {
      console.error("Logo upload error:", error);
      setErrorData({
        title: "Upload Failed",
        list: [error.message || "Failed to upload logo. Please try again."],
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card x-chunk="dashboard-04-chunk-0">
      <CardHeader>
        <CardTitle>Logo Upload</CardTitle>
        <CardDescription>
          Upload your custom logo to display in the header.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Preview Area - shows local preview or uploaded logo */}
          {!isLogoRemoved && (previewUrl || logoUrl) && (
            <div className="flex items-center gap-4">
              <div className="flex h-20 w-20 items-center justify-center rounded-lg border bg-muted">
                {previewUrl ? (
                  // Local file preview (before upload)
                  <img
                    src={previewUrl}
                    alt="Logo preview"
                    className="h-full w-full rounded-lg object-contain"
                  />
                ) : (
                  // Existing logo from database (blob path) - generate signed URL
                  <AppLogoDisplay
                    blobPath={logoUrl}
                    className="h-full w-full rounded-lg object-contain"
                  />
                )}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleRemoveLogo}
              >
                Remove Logo
              </Button>
            </div>
          )}

          {/* Upload Area */}
          <div
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
              isDragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <ForwardedIconComponent
              name="Upload"
              className="mb-4 h-12 w-12 text-muted-foreground"
            />
            <p className="mb-2 text-sm text-muted-foreground">
              Drag and drop your logo here, or
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleBrowseClick}
            >
              Browse Files
            </Button>
            <p className="mt-2 text-xs text-muted-foreground">
              Supported formats: {ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ").toUpperCase()}
            </p>
          </div>

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_IMAGE_INPUT_EXTENSIONS.map((ext) => `.${ext}`).join(",")}
            onChange={handleFileInputChange}
            className="hidden"
          />
        </div>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <Button
          onClick={handleSaveLogo}
          disabled={(!selectedFile && !isLogoRemoved) || isUploading}
          className="w-full sm:w-auto"
        >
          {isUploading ? "Saving..." : "Save"}
        </Button>
      </CardFooter>
    </Card>
  );
};

export default LogoUploadForm;
