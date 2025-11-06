import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ZoomIn, ZoomOut, RotateCw } from "lucide-react";
import LoadingIcon from "@/components/ui/loading";

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileUrl: string;
  fileName: string;
  fileType: string;
}

// Import this component in PlaygroundTab.tsx
// Add after FileUploadManager import:
// import { FilePreviewModal } from "./FilePreviewModal";

export const FilePreviewModal: React.FC<FilePreviewModalProps> = ({
  isOpen,
  onClose,
  fileUrl,
  fileName,
  fileType,
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jsonData, setJsonData] = useState<string>("");
  const [imageScale, setImageScale] = useState(1);
  const [imageRotation, setImageRotation] = useState(0);

  // Determine file type from extension if fileType is not reliable
  const getFileExtension = (filename: string) => {
    return filename.split('.').pop()?.toLowerCase() || '';
  };

  const extension = getFileExtension(fileName);
  const isPNG = fileType.includes('image/png') || extension === 'png';
  const isPDF = fileType.includes('application/pdf') || extension === 'pdf';
  const isJSON = fileType.includes('application/json') || extension === 'json';

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      setError(null);
      setImageScale(1);
      setImageRotation(0);
      
      if (isJSON) {
        fetchJsonData();
      } else {
        setIsLoading(false);
      }
    }
  }, [isOpen, fileUrl]);

  const fetchJsonData = async () => {
    try {
      const response = await fetch(fileUrl);
      if (!response.ok) {
        throw new Error('Failed to fetch JSON file');
      }
      const data = await response.json();
      setJsonData(JSON.stringify(data, null, 2));
      setIsLoading(false);
    } catch (err) {
      setError('Failed to load JSON file');
      setIsLoading(false);
    }
  };

  const handleCopyJson = () => {
    if (jsonData) {
      navigator.clipboard?.writeText(jsonData);
    }
  };

  const handleZoomIn = () => {
    setImageScale(prev => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setImageScale(prev => Math.max(prev - 0.25, 0.5));
  };

  const handleRotate = () => {
    setImageRotation(prev => (prev + 90) % 360);
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="flex h-[60vh] items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <LoadingIcon className="h-8 w-8" />
            <p className="text-sm text-muted-foreground">Loading file...</p>
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" onClick={onClose} className="mt-4">
            </Button>
          </div>
        </div>
      );
    }

    if (isPNG) {
      return (
        <div className="relative h-[70vh] overflow-auto bg-gray-50 dark:bg-gray-900 rounded-md">
          <div className="absolute top-4 right-4 z-10 flex gap-2 bg-white dark:bg-gray-800 rounded-md shadow-md p-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomOut}
              disabled={imageScale <= 0.5}
              className="h-8 w-8 p-0"
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomIn}
              disabled={imageScale >= 3}
              className="h-8 w-8 p-0"
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRotate}
              className="h-8 w-8 p-0"
              title="Rotate"
            >
              <RotateCw className="h-4 w-4" />
            </Button>
            <div className="px-2 flex items-center text-xs text-muted-foreground border-l">
              {Math.round(imageScale * 100)}%
            </div>
          </div>
          
          <div className="flex items-center justify-center min-h-full p-8">
            <img
              src={fileUrl}
              alt={fileName}
              style={{
                transform: `scale(${imageScale}) rotate(${imageRotation}deg)`,
                transition: 'transform 0.2s ease-in-out',
                maxWidth: '100%',
                height: 'auto',
              }}
              onLoad={() => setIsLoading(false)}
              onError={() => setError('Failed to load image')}
            />
          </div>
        </div>
      );
    }

    if (isPDF) {
      return (
        <div className="h-[70vh] w-full">
          <iframe
            src={fileUrl}
            className="h-full w-full rounded-md border-0"
            title={fileName}
            onLoad={() => setIsLoading(false)}
            onError={() => setError('Failed to load PDF')}
          />
        </div>
      );
    }

    if (isJSON) {
      return (
        <div className="relative h-[70vh]">
          <div className="absolute top-2 right-2 z-10">
            <Button
              onClick={handleCopyJson}
              size="sm"
              variant="outline"
              className="bg-white hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 shadow-sm"
            >
              Copy JSON
            </Button>
          </div>
          <pre className="h-full overflow-auto bg-gray-50 dark:bg-gray-900 p-4 pr-24 rounded-md text-xs font-mono border border-gray-200 dark:border-gray-700">
            <code className="text-gray-800 dark:text-gray-200">{jsonData}</code>
          </pre>
        </div>
      );
    }

    return (
      <div className="flex h-[60vh] items-center justify-center">
        <p className="text-sm text-muted-foreground">
          Preview not available for this file type
        </p>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold truncate">
            {fileName}
          </DialogTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
            <span className="px-2 py-1 bg-muted rounded text-xs font-medium uppercase">
              {extension}
            </span>
          </div>
        </DialogHeader>

        {renderContent()}
      </DialogContent>
    </Dialog>
  );
};