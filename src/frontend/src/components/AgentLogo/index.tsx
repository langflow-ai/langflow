import { useGenerateSignedUrl } from "@/hooks/useGenerateSignedUrl";

interface AgentLogoProps {
  blobPath: string | null;
  updatedAt?: string | null;  // ISO timestamp of when logo was last updated
  altText: string;
  className?: string;
}

/**
 * Component to display agent logos with automatic signed URL generation.
 * Handles loading states and errors gracefully.
 *
 * The updatedAt timestamp enables immediate cache invalidation across all users.
 * When any user updates the logo, the timestamp changes, causing all other users
 * to fetch the new logo on their next navigation/refresh.
 *
 * @param blobPath - The blob path stored in database (e.g., "agent-logos/logo-xxxxx.png")
 * @param updatedAt - ISO timestamp when logo was last updated (for cache invalidation)
 * @param altText - Alt text for the image
 * @param className - Optional className for the container (default: "h-12 w-12")
 *
 * @example
 * <AgentLogo
 *   blobPath="agent-logos/logo-123.png"
 *   updatedAt="2025-10-28T10:30:00Z"
 *   altText="My Agent Logo"
 *   className="h-16 w-16"
 * />
 */
export const AgentLogo = ({
  blobPath,
  updatedAt,
  altText,
  className = "h-12 w-12"
}: AgentLogoProps) => {
  const { data: signedUrl, isLoading, isError } = useGenerateSignedUrl({ blobPath, updatedAt });

  // Don't render anything if no blob path
  if (!blobPath) return null;

  // Show loading skeleton while generating signed URL
  if (isLoading) {
    return (
      <div
        className={`${className} flex-shrink-0 rounded-lg border bg-muted overflow-hidden animate-pulse`}
      />
    );
  }

  // Don't render if failed to generate URL or no URL returned
  if (isError || !signedUrl) return null;

  return (
    <div className={`${className} flex-shrink-0 rounded-lg border bg-muted overflow-hidden`}>
      <img
        src={signedUrl}
        alt={altText}
        className="h-full w-full object-contain p-1"
        onError={(e) => {
          // Hide broken images
          e.currentTarget.style.display = "none";
        }}
      />
    </div>
  );
};
