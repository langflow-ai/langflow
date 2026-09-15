import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useAddTeamMember,
  useGetTeamMembers,
  useRemoveTeamMember,
  useUpdateTeamMemberRole,
} from "@/controllers/API/queries/teams";
import type { AuthorizationTeam, TeamRole } from "@/types/authz";
import { TeamMemberPicker } from "../team-member-picker";

const allRoles: TeamRole[] = ["admin", "maintainer", "user"];
const memberPageSize = 50;
const memberPageRequestSize = memberPageSize + 1;

export function TeamMembersSection({
  team,
  onMutationError,
  onMutationStart,
}: {
  team: AuthorizationTeam;
  onMutationError: (error: unknown) => void;
  onMutationStart: () => void;
}) {
  const { t } = useTranslation();
  const [memberOffset, setMemberOffset] = useState(0);
  const membersQuery = useGetTeamMembers({
    teamId: team.id,
    limit: memberPageRequestSize,
    offset: memberOffset,
  });
  const addMember = useAddTeamMember({ onError: onMutationError });
  const updateRole = useUpdateTeamMemberRole({ onError: onMutationError });
  const removeMember = useRemoveTeamMember({ onError: onMutationError });
  const members = membersQuery.data?.slice(0, memberPageSize) ?? [];
  const hasNextPage = (membersQuery.data?.length ?? 0) > memberPageSize;
  const canAdd = team.capabilities.can_add_user_member;
  const allowedAddRoles = team.capabilities.can_add_privileged_member
    ? allRoles
    : (["user"] as TeamRole[]);

  return (
    <section
      aria-labelledby="team-members-heading"
      className="space-y-3 border-t pt-4"
    >
      <h3 id="team-members-heading" className="font-semibold">
        {t("teams.members")}
      </h3>
      {canAdd && (
        <TeamMemberPicker
          teamId={team.id}
          allowedRoles={allowedAddRoles}
          excludedUserIds={membersQuery.data?.map((member) => member.user_id)}
          disabled={addMember.isPending}
          onAdd={(recipient, role) => {
            onMutationStart();
            addMember.mutate({
              teamId: team.id,
              member: { user_id: recipient.id, role },
            });
          }}
        />
      )}
      {membersQuery.isLoading ? (
        <p role="status">{t("teams.loading")}</p>
      ) : membersQuery.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{t("teams.error")}</AlertDescription>
        </Alert>
      ) : members.length ? (
        <ul className="divide-y rounded-lg border">
          {members.map((member) => {
            const manual = member.source === "manual";
            const canChange = team.capabilities.can_change_roles;
            const canRemove =
              manual &&
              (member.role === "user"
                ? team.capabilities.can_remove_user_member
                : team.capabilities.can_change_roles);
            const memberName = member.display_name ?? member.user_id;
            return (
              <li
                key={member.id}
                className="flex flex-wrap items-center gap-3 p-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {memberName}
                  </div>
                  <Badge
                    variant={manual ? "secondaryStatic" : "outline"}
                    size="tag"
                    className="mt-1"
                  >
                    {manual
                      ? t("teams.source.manual")
                      : t("teams.source.external")}
                  </Badge>
                </div>
                <Select
                  value={member.role}
                  disabled={!canChange || updateRole.isPending}
                  onValueChange={(value) => {
                    onMutationStart();
                    updateRole.mutate({
                      teamId: team.id,
                      userId: member.user_id,
                      role: value as TeamRole,
                    });
                  }}
                >
                  <SelectTrigger className="w-36" aria-label={t("teams.role")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {allRoles.map((role) => (
                      <SelectItem key={role} value={role}>
                        {t(`teams.role.${role}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {canRemove && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    loading={removeMember.isPending}
                    aria-label={t("teams.removeMember", {
                      member: memberName,
                    })}
                    onClick={() => {
                      onMutationStart();
                      removeMember.mutate({
                        teamId: team.id,
                        userId: member.user_id,
                      });
                    }}
                  >
                    {t("sharing.remove")}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{t("teams.noMembers")}</p>
      )}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={memberOffset === 0 || membersQuery.isFetching}
          onClick={() =>
            setMemberOffset((offset) => Math.max(0, offset - memberPageSize))
          }
        >
          {t("teams.previous")}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasNextPage || membersQuery.isFetching}
          onClick={() => setMemberOffset((offset) => offset + memberPageSize)}
        >
          {t("teams.next")}
        </Button>
      </div>
    </section>
  );
}
