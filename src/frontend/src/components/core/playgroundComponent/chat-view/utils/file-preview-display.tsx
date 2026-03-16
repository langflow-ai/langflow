import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import { cn } from "@/utils/utils";
import {
  extractFileInfo,
  formatFileName,
  getFilePreviewUrl,
} from "./file-utils";

export type FilePreviewDisplayProps = {
  /**
   * File can be:
   * - Browser File object (for input context)
   * - Server file path object { path: string; type: string; name: string }
   * - Server file path string
   */
  file: File | { path: string; type: string; name: string } | string;
  /**
   * Loading state (for input context when file is being processed)
   */
  loading?: boolean;
  /**
   * Error state (for input context)
   */
  error?: boolean;
  /**
   * Show delete button (only for input context)
   */
  showDelete?: boolean;
  /**
   * Delete callback (only used if showDelete is true)
   */
  onDelete?: () => void;
  /**
   * Variant: "compact" for input, "expanded" for messages
   */
  variant?: "compact" | "expanded";
  /**
   * Custom className
   */
  className?: string;
};

/**
 * Unified file preview display component that handles both:
 * - Input context: Browser File objects with delete functionality
 * - Message context: Server file paths (read-only)
 */
export default function FilePreviewDisplay({
  file,
  loading = false,
  error = false,
  showDelete = false,
  onDelete,
  variant = "compact",
  className,
}: FilePreviewDisplayProps) {
  const [imageError, setImageError] = useState(false);
  const previewUrl = getFilePreviewUrl(file);
  const fileInfo = extractFileInfo(file);

  // Reset error state when file changes
  useEffect(() => {
    setImageError(false);
  }, [file]);

  // Cleanup blob URLs for File objects
  useEffect(() => {
    return () => {
      // Only cleanup blob URLs from File objects
      if (
        file instanceof File &&
        previewUrl &&
        previewUrl.startsWith("blob:")
      ) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [file, previewUrl]);

  // Compact variant (for input-wrapper)
  if (variant === "compact") {
    return (
      <div
        className={cn(
          "relative flex h-16 w-16 items-center justify-center rounded-md border bg-muted",
          error && "border-error",
          className,
        )}
      >
        {loading ? (
          <Loading className="h-4 w-4" />
        ) : previewUrl && !imageError ? (
          <img
            src={previewUrl}
            alt={fileInfo.name}
            className="h-full w-full rounded-md object-cover"
            crossOrigin={file instanceof File ? undefined : "use-credentials"}
            onError={() => {
              setImageError(true);
              console.error("Failed to load image:", previewUrl);
            }}
          />
        ) : (
          <ForwardedIconComponent name="File" className="h-6 w-6" />
        )}

        {showDelete && onDelete && (
          <button
            onClick={onDelete}
            className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90"
            type="button"
            aria-label="Delete file"
          >
            <ForwardedIconComponent name="X" className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  // Expanded variant (for user-message)
  return (
    <div
      className={cn(
        "relative flex w-full lg:w-1/2 items-center justify-center rounded-md border bg-muted",
        error && "border-error",
        className,
      )}
    >
      {loading ? (
        <Loading className="h-4 w-4" />
      ) : previewUrl && !imageError ? (
        <img
          src={previewUrl}
          alt={fileInfo.name}
          className="h-full w-full rounded-md object-cover"
          crossOrigin={file instanceof File ? undefined : "use-credentials"}
          onError={() => {
            setImageError(true);
            console.error("Failed to load image:", previewUrl);
          }}
        />
      ) : (
        <div className="flex flex-col items-center gap-1">
          <ForwardedIconComponent name="File" className="h-6 w-6" />
          <span className="text-xs text-muted-foreground">
            {formatFileName(fileInfo.name, 10)}
          </span>
        </div>
      )}

      {showDelete && onDelete && (
        <button
          onClick={onDelete}
          className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90"
          type="button"
          aria-label="Delete file"
        >
          <ForwardedIconComponent name="X" className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
