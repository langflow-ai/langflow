import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import { customGetAccessToken } from "@/customization/utils/custom-get-access-token";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
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
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isLoadingBlob, setIsLoadingBlob] = useState(false);
  const previewUrl = getFilePreviewUrl(file);
  const fileInfo = extractFileInfo(file);

  // Reset error state when file changes
  useEffect(() => {
    setImageError(false);
    setBlobUrl(null);
  }, [file]);

  // For server file paths (not File objects), fetch and convert to blob URL
  useEffect(() => {
    if (
      previewUrl &&
      !(file instanceof File) &&
      !blobUrl &&
      !isLoadingBlob &&
      !imageError
    ) {
      setIsLoadingBlob(true);

      // Prepare fetch options with credentials and auth headers
      const accessToken = customGetAccessToken();
      const fetchOptions: RequestInit = {
        credentials: getFetchCredentials(),
      };

      if (accessToken) {
        fetchOptions.headers = {
          Authorization: `Bearer ${accessToken}`,
        };
      }

      fetch(previewUrl, fetchOptions)
        .then((response) => {
          if (!response.ok) {
            throw new Error(
              `Failed to fetch image: ${response.status} ${response.statusText}`,
            );
          }
          return response.blob();
        })
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          setBlobUrl(url);
          setIsLoadingBlob(false);
        })
        .catch((err) => {
          console.error("Failed to load image as blob:", err);
          setImageError(true);
          setIsLoadingBlob(false);
        });
    }

    // Cleanup blob URL on unmount or when file changes
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [file, previewUrl, blobUrl, isLoadingBlob, imageError]);

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
        {loading || isLoadingBlob ? (
          <Loading className="h-4 w-4" />
        ) : previewUrl &&
          (file instanceof File ? previewUrl : blobUrl) &&
          !imageError ? (
          <img
            src={(file instanceof File ? previewUrl : blobUrl) ?? undefined}
            alt={fileInfo.name}
            className="h-full w-full rounded-md object-cover"
            onError={() => {
              setImageError(true);
              console.error(
                "Failed to load image:",
                file instanceof File ? previewUrl : blobUrl,
              );
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
        "relative flex h-16 w-16 items-center justify-center rounded-md border bg-muted",
        error && "border-error",
        className,
      )}
    >
      {loading || isLoadingBlob ? (
        <Loading className="h-4 w-4" />
      ) : previewUrl &&
        (file instanceof File ? previewUrl : blobUrl) &&
        !imageError ? (
        <img
          src={(file instanceof File ? previewUrl : blobUrl) ?? undefined}
          alt={fileInfo.name}
          className="h-full w-full rounded-md object-cover"
          onError={() => {
            setImageError(true);
            console.error(
              "Failed to load image:",
              file instanceof File ? previewUrl : blobUrl,
            );
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
