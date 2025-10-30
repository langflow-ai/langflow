import React, { useState, useRef } from "react";
import { v4 as uuid } from "uuid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Upload, X } from "lucide-react";
import LoadingIcon from "@/components/ui/loading";
import { usePostReadPresignedUrl, usePostUploadPresignedUrl, useUploadToBlob } from "@/controllers/API/queries/flexstore";

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
  const [uploadedFiles, setUploadedFiles] = useState<Record<string, UploadedFile[]>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [currentUploadComponentId, setCurrentUploadComponentId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Mutation hooks for file operations
  const uploadPresignedUrlMutation = usePostUploadPresignedUrl();
  const uploadToBlobMutation = useUploadToBlob();
  const readPresignedUrlMutation = usePostReadPresignedUrl();

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // File upload handler
  const handleFileUpload = async (componentId: string) => {
    if (!fileInputRef.current) return;
    
    setCurrentUploadComponentId(componentId);
    fileInputRef.current.accept = "*/*";
    fileInputRef.current.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      setIsUploading(true);
      setUploadProgress({ [componentId]: 0 });

      try {
        // Step 1: Generate upload presigned URL
        const fileName = `agent-sample-run/${uuid()}_${file.name}`;
        const uploadUrlResponse = await uploadPresignedUrlMutation.mutateAsync({
          sourceType: "azureblobstorage",
          fileName,
          sourceDetails: {
            containerName: process.env.FLEXSTORE_DEFAULT_CONTAINERNAME || "ai-studio-v2",
            storageAccount: process.env.FLEXSTORE_DEFAULT_STORAGE_ACCOUNT || "autonomizestorageaccount"
          }
        });

        const uploadUrl = uploadUrlResponse.presignedUrl.data.signedUrl;
        setUploadProgress({ [componentId]: 25 });

        // Step 2: Upload file to blob storage
        await uploadToBlobMutation.mutateAsync({
          presignedUrl: uploadUrl,
          file
        });

        setUploadProgress({ [componentId]: 75 });

        // Step 3: Generate read presigned URL
        const readUrlResponse = await readPresignedUrlMutation.mutateAsync({
          sourceType: "azureblobstorage",
          fileName,
          sourceDetails: {
            containerName: process.env.FLEXSTORE_DEFAULT_CONTAINERNAME || "ai-studio-v2",
            storageAccount: process.env.FLEXSTORE_DEFAULT_STORAGE_ACCOUNT || "autonomizestorageaccount"
          }
        });

        const readUrl = readUrlResponse.presignedUrl.data.signedUrl;
        setUploadProgress({ [componentId]: 100 });

        // Step 4: Create uploaded file record
        const uploadedFile: UploadedFile = {
          id: uuid(),
          name: file.name,
          size: file.size,
          type: file.type,
          readUrl,
          uploadTimestamp: new Date()
        };

        // Step 5: Update uploaded files and set the URL for the component
        setUploadedFiles(prev => ({
          ...prev,
          [componentId]: [...(prev[componentId] || []), uploadedFile]
        }));

        onFileUrlChange(componentId, readUrl);

        console.log(`File uploaded successfully for component ${componentId}:`, {
          fileName,
          readUrl,
          fileSize: file.size,
          fileType: file.type
        });

        // Clear progress after a delay
        setTimeout(() => {
          setUploadProgress({});
        }, 1000);

      } catch (error) {
        console.error("File upload failed:", error);
        onError(`File upload failed: ${error instanceof Error ? error.message : "Unknown error"}`);
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

  // Remove uploaded file
  const removeUploadedFile = (componentId: string, fileId: string) => {
    setUploadedFiles(prev => {
      const componentFiles = prev[componentId] || [];
      const updatedFiles = componentFiles.filter(f => f.id !== fileId);
      
      return {
        ...prev,
        [componentId]: updatedFiles
      };
    });

    // If this was the active file URL, clear it
    const fileToRemove = uploadedFiles[componentId]?.find(f => f.id === fileId);
    if (fileToRemove && fileUrls[componentId] === fileToRemove.readUrl) {
      onClearFileUrl(componentId);
    }
  };

  // Use uploaded file for component
  const useUploadedFile = (componentId: string, file: UploadedFile) => {
    onFileUrlChange(componentId, file.readUrl);
  };

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        style={{ display: 'none' }}
      />

      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Manage File Inputs</DialogTitle>
            <DialogDescription>
              Provide file URLs or upload files for components that require file inputs.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {fileInputComponents.map((component) => (
              <div key={component.id} className="space-y-3 border rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">
                    {component.display_name}
                    <span className="text-xs text-muted-foreground ml-1">
                      ({component.inputKey})
                    </span>
                  </Label>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleFileUpload(component.id)}
                    disabled={isUploading && currentUploadComponentId === component.id}
                    className="flex items-center gap-2"
                  >
                    {isUploading && currentUploadComponentId === component.id ? (
                      <LoadingIcon className="h-4 w-4" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    Upload File
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

                {/* File URL Input */}
                <div className="flex gap-2">
                  <Input
                    placeholder="https://example.com/file.pdf"
                    value={fileUrls[component.id] || ""}
                    onChange={(e) => onFileUrlChange(component.id, e.target.value)}
                    className="flex-1"
                  />
                  {fileUrls[component.id] && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onClearFileUrl(component.id)}
                    >
                      Clear
                    </Button>
                  )}
                </div>

                {/* Uploaded Files List */}
                {uploadedFiles[component.id] && uploadedFiles[component.id].length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Uploaded Files:</p>
                    <div className="space-y-2 max-h-32 overflow-y-auto">
                      {uploadedFiles[component.id].map((file) => (
                        <div key={file.id} className="flex items-center justify-between p-2 bg-muted rounded-md">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{file.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatFileSize(file.size)} • {file.uploadTimestamp.toLocaleString()}
                            </p>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => useUploadedFile(component.id, file)}
                              className="text-xs px-2 py-1 h-auto"
                              disabled={fileUrls[component.id] === file.readUrl}
                            >
                              {fileUrls[component.id] === file.readUrl ? "Active" : "Use"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeUploadedFile(component.id, file.id)}
                              className="text-destructive hover:text-destructive p-1 h-auto"
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-end space-x-2 pt-4">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={onClose}>
              Done
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};