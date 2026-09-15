import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateTeam } from "@/controllers/API/queries/teams";
import type { AuthorizationRecipient, TeamRole } from "@/types/authz";
import { extractApiErrorMessages } from "@/utils/apiError";
import { TeamMemberPicker } from "./team-member-picker";

interface InitialMember {
  recipient: AuthorizationRecipient;
  role: TeamRole;
}

interface TeamCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (teamId: string) => void;
}

const roles: TeamRole[] = ["admin", "maintainer", "user"];

export function TeamCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: TeamCreateDialogProps) {
  const { t } = useTranslation();
  const nameId = useId();
  const domainId = useId();
  const descriptionId = useId();
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [members, setMembers] = useState<InitialMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const createTeam = useCreateTeam({
    onSuccess: (team) => {
      onCreated(team.id);
      onOpenChange(false);
      setName("");
      setDomain("");
      setDescription("");
      setMembers([]);
      setError(null);
    },
    onError: (requestError) =>
      setError(extractApiErrorMessages(requestError).join(" ")),
  });
  const hasAdmin = members.some((member) => member.role === "admin");
  const canSave = Boolean(name.trim() && domain.trim() && hasAdmin);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("teams.createTitle")}</DialogTitle>
          <DialogDescription>{t("teams.createDescription")}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={nameId}>{t("teams.name")}</Label>
            <Input
              id={nameId}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={domainId}>{t("teams.domain")}</Label>
            <Input
              id={domainId}
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={descriptionId}>{t("teams.description")}</Label>
          <Textarea
            id={descriptionId}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        <section
          className="space-y-3"
          aria-labelledby="initial-members-heading"
        >
          <h3 id="initial-members-heading" className="text-sm font-semibold">
            {t("teams.initialMembers")}
          </h3>
          <TeamMemberPicker
            allowedRoles={roles}
            excludedUserIds={members.map((member) => member.recipient.id)}
            onAdd={(recipient, role) =>
              setMembers((current) => [...current, { recipient, role }])
            }
          />
          {members.length > 0 && (
            <ul className="space-y-2">
              {members.map((member) => (
                <li
                  key={member.recipient.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border p-2"
                >
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {member.recipient.display_name}
                  </span>
                  <Select
                    value={member.role}
                    onValueChange={(value) =>
                      setMembers((current) =>
                        current.map((candidate) =>
                          candidate.recipient.id === member.recipient.id
                            ? { ...candidate, role: value as TeamRole }
                            : candidate,
                        ),
                      )
                    }
                  >
                    <SelectTrigger
                      className="w-36"
                      aria-label={t("teams.role")}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roles.map((role) => (
                        <SelectItem key={role} value={role}>
                          {t(`teams.role.${role}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    aria-label={t("teams.removeMember", {
                      member: member.recipient.display_name,
                    })}
                    onClick={() =>
                      setMembers((current) =>
                        current.filter(
                          (candidate) =>
                            candidate.recipient.id !== member.recipient.id,
                        ),
                      )
                    }
                  >
                    {t("sharing.remove")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {!hasAdmin && (
            <Badge variant="errorStatic">{t("teams.adminRequired")}</Badge>
          )}
        </section>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {t("teams.cancel")}
          </Button>
          <Button
            type="button"
            disabled={!canSave}
            loading={createTeam.isPending}
            onClick={() =>
              createTeam.mutate({
                team_name: name.trim(),
                adom_name: domain.trim(),
                description: description.trim() || null,
                is_active: true,
                members: members.map((member) => ({
                  user_id: member.recipient.id,
                  role: member.role,
                })),
              })
            }
          >
            {t("teams.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
