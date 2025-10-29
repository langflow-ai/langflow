import { useGenerateSignedUrl } from "@/hooks/useGenerateSignedUrl";

interface AppLogoDisplayProps {
  blobPath: string | null;
  className?: string;
}

/**
 * Component to display application logo in the header with automatic signed URL generation.
 *
 * This component handles the conversion of blob paths (stored in database) to fresh signed URLs
 * using the Flexstore API. URLs are generated on-demand and cached by React Query.
 *
 * @param blobPath - The blob path stored in database (e.g., "app-logo/logo-xxxxx.png")
 * @param className - Optional className for the image element
 *
 * @example
 * <AppLogoDisplay
 *   blobPath="app-logo/logo-123.png"
 *   className="h-full w-full object-contain"
 * />
 */
export const AppLogoDisplay = ({
  blobPath,
  className = "h-full w-full object-contain"
}: AppLogoDisplayProps) => {
  const { data: signedUrl, isLoading, isError } = useGenerateSignedUrl({ blobPath });

  // Don't render if no blob path
  if (!blobPath) return null;

  // Show loading skeleton while generating signed URL
  if (isLoading) {
    return <div className={`${className} animate-pulse bg-muted rounded`} />;
  }

  // Don't render if failed to generate URL
  if (isError || !signedUrl) return null;

  return (
    <img
      src={signedUrl}
      alt="Custom Logo"
      className={className}
      onError={(e) => {
        // Hide broken images gracefully
        e.currentTarget.style.display = "none";
      }}
    />
  );
};
