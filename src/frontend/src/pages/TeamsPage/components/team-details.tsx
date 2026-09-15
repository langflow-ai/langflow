import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useDeleteTeam,
  useGetTeam,
  useUpdateTeam,
} from "@/controllers/API/queries/teams";
import { extractApiErrorMessages } from "@/utils/apiError";
import { DeleteTeamDialog } from "./team-details/delete-team-dialog";
import { TeamMembersSection } from "./team-details/team-members-section";

export function TeamDetails({
  teamId,
  onDeleted,
}: {
  teamId: string;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const nameId = useId();
  const domainId = useId();
  const descriptionId = useId();
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const teamQuery = useGetTeam(teamId);
  const team = teamQuery.data;

  useEffect(() => {
    if (!team) return;
    setName(team.team_name);
    setDomain(team.adom_name);
    setDescription(team.description ?? "");
  }, [team]);

  const mutationError = (requestError: unknown) =>
    setError(extractApiErrorMessages(requestError).join(" "));
  const updateTeam = useUpdateTeam({ onError: mutationError });
  const deleteTeam = useDeleteTeam({
    onSuccess: () => {
      setDeleteOpen(false);
      onDeleted();
    },
    onError: mutationError,
  });

  if (teamQuery.isLoading) return <p role="status">{t("teams.loading")}</p>;
  if (teamQuery.isError || !team) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{t("teams.error")}</AlertDescription>
      </Alert>
    );
  }

  const canEdit = team.capabilities.can_update;
  const canEditDirectoryMapping = team.capabilities.can_set_active;

  return (
    <section
      className="space-y-5"
      data-testid={`team-details-${team.id}`}
      aria-labelledby={`team-heading-${team.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2
            id={`team-heading-${team.id}`}
            className="break-words text-xl font-semibold"
          >
            {team.team_name}
          </h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge
              variant={team.is_active ? "successStatic" : "secondaryStatic"}
            >
              {team.is_active
                ? t("teams.status.active")
                : t("teams.status.inactive")}
            </Badge>
            {team.current_user_role && (
              <Badge variant="outline">
                {t(`teams.role.${team.current_user_role}`)}
              </Badge>
            )}
          </div>
        </div>
        {team.capabilities.can_delete && (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setDeleteOpen(true)}
          >
            {t("teams.delete")}
          </Button>
        )}
      </div>

      {team.inactivation_reason === "no_active_admin" && (
        <Alert>
          <AlertDescription>{t("teams.noActiveAdmin")}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="team-details-heading" className="space-y-3">
        <h3 id="team-details-heading" className="font-semibold">
          {t("teams.details")}
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={nameId}>{t("teams.name")}</Label>
            <Input
              id={nameId}
              value={name}
              disabled={!canEdit}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={domainId}>{t("teams.domain")}</Label>
            <Input
              id={domainId}
              value={domain}
              disabled={!canEditDirectoryMapping}
              onChange={(event) => setDomain(event.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={descriptionId}>{t("teams.description")}</Label>
          <Textarea
            id={descriptionId}
            value={description}
            disabled={!canEdit}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {team.capabilities.can_set_active && (
          <div className="flex items-center gap-3">
            <Switch
              id={`team-active-${team.id}`}
              className="forced-colors:[&>span]:border forced-colors:[&>span]:border-[ButtonText]"
              checked={team.is_active}
              disabled={updateTeam.isPending}
              onCheckedChange={(checked) => {
                setError(null);
                updateTeam.mutate({ teamId, data: { is_active: checked } });
              }}
            />
            <Label htmlFor={`team-active-${team.id}`}>
              {t("teams.active")}
            </Label>
          </div>
        )}
        {canEdit && (
          <Button
            type="button"
            loading={updateTeam.isPending}
            disabled={!name.trim() || !domain.trim()}
            onClick={() => {
              setError(null);
              updateTeam.mutate({
                teamId,
                data: {
                  team_name: name.trim(),
                  description: description.trim() || null,
                  ...(canEditDirectoryMapping
                    ? { adom_name: domain.trim() }
                    : {}),
                },
              });
            }}
          >
            {t("teams.save")}
          </Button>
        )}
      </section>

      <TeamMembersSection
        key={team.id}
        team={team}
        onMutationStart={() => setError(null)}
        onMutationError={mutationError}
      />

      <DeleteTeamDialog
        team={team}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        loading={deleteTeam.isPending}
        onDelete={() => deleteTeam.mutate({ teamId })}
      />
    </section>
  );
}
