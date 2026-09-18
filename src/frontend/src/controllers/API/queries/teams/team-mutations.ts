import type { useMutationFunctionType } from "@/types/api";
import type {
  AuthorizationTeam,
  AuthorizationTeamMember,
  TeamCreateInput,
  TeamMemberInput,
  TeamRole,
  TeamUpdateInput,
} from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { invalidateAuthorizationState } from "../authorization";

export const useCreateTeam: useMutationFunctionType<
  undefined,
  TeamCreateInput,
  AuthorizationTeam
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["createAuthorizationTeam"],
    async (payload: TeamCreateInput) => {
      const { data } = await api.post<AuthorizationTeam>(
        getURL("AUTHZ_TEAMS"),
        payload,
      );
      return data;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};

export const useUpdateTeam: useMutationFunctionType<
  undefined,
  { teamId: string; data: TeamUpdateInput },
  AuthorizationTeam
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["updateAuthorizationTeam"],
    async ({ teamId, data }: { teamId: string; data: TeamUpdateInput }) => {
      const response = await api.patch<AuthorizationTeam>(
        `${getURL("AUTHZ_TEAMS")}/${teamId}`,
        data,
      );
      return response.data;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};

export const useDeleteTeam: useMutationFunctionType<
  undefined,
  { teamId: string },
  string
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["deleteAuthorizationTeam"],
    async ({ teamId }: { teamId: string }) => {
      await api.delete(`${getURL("AUTHZ_TEAMS")}/${teamId}`);
      return teamId;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};

export const useAddTeamMember: useMutationFunctionType<
  undefined,
  { teamId: string; member: TeamMemberInput },
  AuthorizationTeamMember
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["addAuthorizationTeamMember"],
    async ({ teamId, member }: { teamId: string; member: TeamMemberInput }) => {
      const { data } = await api.post<AuthorizationTeamMember>(
        `${getURL("AUTHZ_TEAMS")}/${teamId}/members`,
        member,
      );
      return data;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};

export const useUpdateTeamMemberRole: useMutationFunctionType<
  undefined,
  { teamId: string; userId: string; role: TeamRole },
  AuthorizationTeamMember
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["updateAuthorizationTeamMemberRole"],
    async ({
      teamId,
      userId,
      role,
    }: {
      teamId: string;
      userId: string;
      role: TeamRole;
    }) => {
      const { data } = await api.patch<AuthorizationTeamMember>(
        `${getURL("AUTHZ_TEAMS")}/${teamId}/members/${userId}`,
        { role },
      );
      return data;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};

export const useRemoveTeamMember: useMutationFunctionType<
  undefined,
  { teamId: string; userId: string },
  string
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["removeAuthorizationTeamMember"],
    async ({ teamId, userId }: { teamId: string; userId: string }) => {
      await api.delete(`${getURL("AUTHZ_TEAMS")}/${teamId}/members/${userId}`);
      return userId;
    },
    {
      ...options,
      onSuccess: async (...args) => {
        await invalidateAuthorizationState(queryClient);
        await options?.onSuccess?.(...args);
      },
    },
  );
};
