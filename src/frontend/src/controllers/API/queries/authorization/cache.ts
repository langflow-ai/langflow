import type { QueryClient } from "@tanstack/react-query";
import type { ShareResourceType } from "@/types/authz";

export async function invalidateAuthorizationState(
  queryClient: QueryClient,
  resource?: { type: ShareResourceType; id: string },
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["authorizationCapabilities"] }),
    queryClient.invalidateQueries({ queryKey: ["authorizationRecipients"] }),
    queryClient.invalidateQueries({
      queryKey: ["authorizationSharedResources"],
    }),
    queryClient.invalidateQueries({ queryKey: ["authorizationTeams"] }),
    queryClient.invalidateQueries({ queryKey: ["authorizationTeam"] }),
    queryClient.invalidateQueries({ queryKey: ["authorizationTeamMembers"] }),
    queryClient.invalidateQueries({ queryKey: ["authorizationShareSummary"] }),
    queryClient.invalidateQueries({ queryKey: ["useGetEffectivePermissions"] }),
    queryClient.invalidateQueries({ queryKey: ["useGetRefreshFlowsQuery"] }),
    queryClient.invalidateQueries({ queryKey: ["useGetFolders"] }),
    ...(resource
      ? [
          queryClient.invalidateQueries({
            queryKey: ["authorizationShareSummary", resource.type, resource.id],
          }),
        ]
      : []),
  ]);
}
