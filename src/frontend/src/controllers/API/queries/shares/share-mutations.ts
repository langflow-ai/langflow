import type { useMutationFunctionType } from "@/types/api";
import type {
  AuthorizationShare,
  ShareDialogPermission,
  ShareRecipientType,
  ShareResourceType,
} from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { invalidateAuthorizationState } from "../authorization";

const shareEtag = (shareId: string, revision: number) =>
  `"share:${shareId}:${revision}"`;

export const useCreateShare: useMutationFunctionType<
  undefined,
  {
    resourceType: ShareResourceType;
    resourceId: string;
    recipientType: ShareRecipientType;
    recipientId: string;
    permission: ShareDialogPermission;
  },
  AuthorizationShare
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["createAuthorizationShare"],
    async ({
      resourceType,
      resourceId,
      recipientType,
      recipientId,
      permission,
    }) => {
      const { data } = await api.post<AuthorizationShare>(
        getURL("AUTHZ_SHARES"),
        {
          resource_type: resourceType,
          resource_id: resourceId,
          scope: recipientType,
          target_id: recipientId,
          permission_level: permission,
        },
      );
      return data;
    },
    {
      ...options,
      onSuccess: async (data, variables, ...rest) => {
        await invalidateAuthorizationState(queryClient, {
          type: variables.resourceType,
          id: variables.resourceId,
        });
        await options?.onSuccess?.(data, variables, ...rest);
      },
    },
  );
};

export const useUpdateShare: useMutationFunctionType<
  undefined,
  {
    shareId: string;
    revision: number;
    resourceType: ShareResourceType;
    resourceId: string;
    permission: ShareDialogPermission;
  },
  AuthorizationShare
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["updateAuthorizationShare"],
    async ({ shareId, revision, permission }) => {
      const { data } = await api.patch<AuthorizationShare>(
        `${getURL("AUTHZ_SHARES")}/${shareId}`,
        { permission_level: permission },
        { headers: { "If-Match": shareEtag(shareId, revision) } },
      );
      return data;
    },
    {
      ...options,
      onSuccess: async (data, variables, ...rest) => {
        await invalidateAuthorizationState(queryClient, {
          type: variables.resourceType,
          id: variables.resourceId,
        });
        await options?.onSuccess?.(data, variables, ...rest);
      },
    },
  );
};

export const useDeleteShare: useMutationFunctionType<
  undefined,
  {
    shareId: string;
    revision: number;
    resourceType: ShareResourceType;
    resourceId: string;
  },
  string
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["deleteAuthorizationShare"],
    async ({ shareId, revision }) => {
      await api.delete(`${getURL("AUTHZ_SHARES")}/${shareId}`, {
        headers: { "If-Match": shareEtag(shareId, revision) },
      });
      return shareId;
    },
    {
      ...options,
      onSuccess: async (data, variables, ...rest) => {
        await invalidateAuthorizationState(queryClient, {
          type: variables.resourceType,
          id: variables.resourceId,
        });
        await options?.onSuccess?.(data, variables, ...rest);
      },
    },
  );
};
