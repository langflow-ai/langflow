import React, { useState, useRef } from "react";
import { v4 as uuid } from "uuid";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import LoadingIcon from "@/components/ui/loading";
import {
  usePostReadPresignedUrl,
  usePostUploadPresignedUrl,
  useUploadToBlob,
} from "@/controllers/API/queries/flexstore";
import { RiUploadCloud2Fill } from "react-icons/ri";
import { envConfig } from "@/config/env";

interface FileInputComponent {
  id: string;
  type: string;
  display_name: string;
  inputKey: string;
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  readUrl: string;
  uploadTimestamp: Date;
}

interface FileUploadManagerProps {
  isOpen: boolean;
  onClose: () => void;
  fileInputComponents: FileInputComponent[];
  fileUrls: Record<string, string>;
  onFileUrlChange: (componentId: string, url: string) => void;
  onClearFileUrl: (componentId: string) => void;
  onError: (error: string) => void;
}

export const FileUploadManager: React.FC<FileUploadManagerProps> = ({
  isOpen,
  onClose,
  fileInputComponents,
  fileUrls,
  onFileUrlChange,
  onClearFileUrl,
  onError,
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>(
    {}
  );
  const [currentUploadComponentId, setCurrentUploadComponentId] = useState<
    string | null
  >(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadPresignedUrlMutation = usePostUploadPresignedUrl();
  const uploadToBlobMutation = useUploadToBlob();
  const readPresignedUrlMutation = usePostReadPresignedUrl();

  const handleFileUpload = async (componentId: string) => {
    if (!fileInputRef.current) return;

    setCurrentUploadComponentId(componentId);
    fileInputRef.current.accept =
      ".json,.png,.pdf,application/json,image/png,application/pdf";
    fileInputRef.current.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      // Validate file type
      const allowedTypes = ["application/json", "image/png", "application/pdf"];
      const allowedExtensions = [".json", ".png", ".pdf"];
      const fileExtension = "." + file.name.split(".").pop()?.toLowerCase();

      if (
        !allowedTypes.includes(file.type) &&
        !allowedExtensions.includes(fileExtension)
      ) {
        onError(
          "Invalid file type. Only JSON, PNG, and PDF files are accepted."
        );
        setCurrentUploadComponentId(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        return;
      }

      setIsUploading(true);
      setUploadProgress({ [componentId]: 0 });

      try {
        const fileName = `agent-sample-run/${uuid()}_${file.name}`;
        const uploadUrlResponse = await uploadPresignedUrlMutation.mutateAsync({
          sourceType: "azureblobstorage",
          fileName,
          sourceDetails: {
            containerName: envConfig.flexstoreDefaultTemporaryStorageContainer,
            storageAccount: envConfig.flexstoreDefaultTemporaryStorageAccount
          },
        });

        const uploadUrl = uploadUrlResponse.presignedUrl.data.signedUrl;
        setUploadProgress({ [componentId]: 25 });

        await uploadToBlobMutation.mutateAsync({
          presignedUrl: uploadUrl,
          file,
        });

        setUploadProgress({ [componentId]: 75 });

        const readUrlResponse = await readPresignedUrlMutation.mutateAsync({
          sourceType: "azureblobstorage",
          fileName,
          sourceDetails: {
            containerName: envConfig.flexstoreDefaultTemporaryStorageContainer,
            storageAccount: envConfig.flexstoreDefaultTemporaryStorageAccount
          },
        });

        const readUrl = readUrlResponse.presignedUrl.data.signedUrl;
        setUploadProgress({ [componentId]: 100 });

        // Replace existing file URL for this component
        onFileUrlChange(componentId, readUrl);

        console.log(
          `File uploaded successfully for component ${componentId}:`,
          {
            fileName,
            readUrl,
            fileSize: file.size,
            fileType: file.type,
          }
        );

        // Close modal after successful upload
        setTimeout(() => {
          setUploadProgress({});
          onClose();
        }, 500);
      } catch (error) {
        console.error("File upload failed:", error);
        onError(
          `File upload failed: ${
            error instanceof Error ? error.message : "Unknown error"
          }`
        );
        setUploadProgress({});
      } finally {
        setIsUploading(false);
        setCurrentUploadComponentId(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    };

    fileInputRef.current.click();
  };

  const handleClose = () => {
    if (!isUploading) {
      onClose();
    }
  };

  return (
    <>
      {/* Hidden file input */}
      <input ref={fileInputRef} type="file" style={{ display: "none" }} />

      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Manage File Inputs</DialogTitle>
            <DialogDescription>
              Upload files for components that require file inputs.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {fileInputComponents.map((component) => (
              <div key={component.id} className="space-y-3">
                <div className="mt-4">
                  <Label className="text-sm font-medium">
                    {component.display_name}
                  </Label>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleFileUpload(component.id)}
                    disabled={isUploading}
                    className={`flex flex-col h-auto !py-10 mt-2 w-full cursor-pointer items-center justify-center gap-2 rounded-lg hover:bg-transparent border-2 border-primary-border hover:border-secondary-border border-dashed p-8 transition-colors `}
                  >
                    {isUploading &&
                    currentUploadComponentId === component.id ? (
                      <LoadingIcon className="h!h-14 !w-14" />
                    ) : (
                      <RiUploadCloud2Fill className="!h-14 !w-14 text-secondary-font opacity-70" />
                    )}
                    <p>
                      <span className="text-sm font-medium text-secondary-font block">
                        Upload File
                      </span>
                      <span className="text-[11px] text-secondary-font italic opacity-70 block">
                        Accepted file types: JSON, PNG, PDF
                      </span>
                    </p>
                  </Button>
                </div>

                {/* Upload Progress */}
                {uploadProgress[component.id] !== undefined && (
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress[component.id]}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
