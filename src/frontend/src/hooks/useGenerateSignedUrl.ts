import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getBackendUrl } from "@/config/constants";
import { envConfig } from "@/config/env";
import { env } from "process";

interface GenerateSignedUrlParams {
  blobPath: string | null;
  updatedAt?: string | null;  // ISO timestamp of when logo was last updated
  enabled?: boolean;
}

/**
 * Hook to generate fresh signed URLs from Azure blob paths using BFF Flexstore API.
 *
 * The updatedAt timestamp is included in the cache key to ensure immediate cache invalidation
 * when a logo is updated by any user. When the timestamp changes, the cache key changes,
 * triggering a refetch of the new signed URL.
 *
 * @param blobPath - The blob path (e.g., "agent-logos/logo-xxxxx.png")
 * @param updatedAt - ISO timestamp when logo was last updated (for cache invalidation)
 * @param enabled - Whether to enable the query (default: true)
 * @returns React Query result with signed URL
 *
 * @example
 * const { data: signedUrl, isLoading } = useGenerateSignedUrl({
 *   blobPath: "agent-logos/logo-123.png",
 *   updatedAt: "2025-10-28T10:30:00Z"
 * });
 */
export const useGenerateSignedUrl = ({
  blobPath,
  updatedAt,
  enabled = true
}: GenerateSignedUrlParams) => {
  return useQuery({
    queryKey: ["signed-url", blobPath, updatedAt],
    queryFn: async () => {
      if (!blobPath) return null;
      debugger;

      const response = await api.post(`${getBackendUrl()}/api/v1/flexstore/signedurl/read`, {
        sourceType: "azureblobstorage",
        fileName: blobPath,
        sourceDetails: {
          containerName: envConfig.flexstoreDefaultTemporaryStorageContainer,
          storageAccount: envConfig.flexstoreDefaultTemporaryStorageAccount,
        },
      });

      return response.data.presignedUrl.data.signedUrl;
    },
    enabled: enabled && !!blobPath,
    staleTime: 0, // 1 hour cache (URLs valid for 24h)
    refetchOnWindowFocus: true, // Refetch when user returns to tab (if stale)
    refetchOnReconnect: true, // Refetch when internet reconnects (if stale)
    retry: 1, // Retry failed requests twice
  });
};
