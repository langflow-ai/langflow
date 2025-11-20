import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface ValidateMarketplaceNameParams {
  marketplaceName: string;
  excludeFlowId?: string;
  folderId?: string;
  enabled?: boolean;
}

interface ValidateMarketplaceNameResponse {
  exists: boolean;
  available: boolean;
  message?: string;
}

/**
 * Hook to validate if a marketplace flow name already exists.
 * Uses debouncing via staleTime to avoid excessive API calls.
 *
 * Performs two checks:
 * 1. Global marketplace name uniqueness in published_flow table
 * 2. Folder-scoped flow name uniqueness in flow table
 *
 * @param marketplaceName - The marketplace flow name to validate
 * @param excludeFlowId - Optional flow ID to exclude from validation (for re-publishing)
 * @param folderId - Folder ID for folder-scoped validation
 * @param enabled - Whether to enable the query (default: true when marketplaceName is not empty)
 * @returns React Query result with validation status
 */
export const useValidateMarketplaceName = ({
  marketplaceName,
  excludeFlowId,
  folderId,
  enabled = true,
}: ValidateMarketplaceNameParams) => {
  return useQuery<ValidateMarketplaceNameResponse>({
    queryKey: ["validate-marketplace-name", marketplaceName, excludeFlowId, folderId],
    queryFn: async () => {
      const response = await api.post<ValidateMarketplaceNameResponse>(
        `${getURL("PUBLISHED_FLOWS")}/validate-name`,
        {
          marketplace_flow_name: marketplaceName,
          exclude_flow_id: excludeFlowId,
          folder_id: folderId,
        }
      );
      return response.data;
    },
    // Only run validation if name is not empty and enabled
    enabled: enabled && marketplaceName.trim().length > 0,
    // Debouncing: Cache for 500ms to avoid excessive API calls while typing
    staleTime: 500,
    // Don't cache results for too long as availability can change
    gcTime: 1000 * 60, // 1 minute
    // Don't retry on validation errors
    retry: false,
    // Refetch when window regains focus to ensure freshness
    refetchOnWindowFocus: true,
  });
};
