import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { ShareResourceType, ShareSummary } from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetShareSummaryParams {
  resourceType: ShareResourceType;
  resourceId: string;
  subjectUserId?: string;
  limit?: number;
  offset?: number;
}

export const useGetShareSummary: useQueryFunctionType<
  GetShareSummaryParams,
  ShareSummary
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    [
      "authorizationShareSummary",
      params.resourceType,
      params.resourceId,
      userId ?? "anonymous",
      params.subjectUserId ?? null,
      params.limit ?? 50,
      params.offset ?? 0,
    ],
    async () => {
      const { data } = await api.get<ShareSummary>(
        `${getURL("AUTHZ_SHARES")}/summary`,
        {
          params: {
            resource_type: params.resourceType,
            resource_id: params.resourceId,
            subject_user_id: params.subjectUserId,
            limit: params.limit ?? 50,
            offset: params.offset ?? 0,
          },
        },
      );
      return data;
    },
    {
      staleTime: 15_000,
      ...options,
      enabled:
        Boolean(userId && params.resourceId) && (options?.enabled ?? true),
    },
  );
};
