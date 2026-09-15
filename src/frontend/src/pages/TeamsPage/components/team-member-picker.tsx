import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSearchAuthorizationRecipients } from "@/controllers/API/queries/authorization";
import type { AuthorizationRecipient, TeamRole } from "@/types/authz";

interface TeamMemberPickerProps {
  teamId?: string;
  allowedRoles: TeamRole[];
  excludedUserIds?: string[];
  onAdd: (recipient: AuthorizationRecipient, role: TeamRole) => void;
  disabled?: boolean;
}

function useDebouncedSearch(value: string): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), 300);
    return () => window.clearTimeout(timer);
  }, [value]);
  return debounced;
}

export function TeamMemberPicker({
  teamId,
  allowedRoles,
  excludedUserIds = [],
  onAdd,
  disabled = false,
}: TeamMemberPickerProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuthorizationRecipient | null>(null);
  const [role, setRole] = useState<TeamRole>(
    allowedRoles.includes("user") ? "user" : allowedRoles[0],
  );
  const debounced = useDebouncedSearch(search);
  const recipients = useSearchAuthorizationRecipients(
    {
      purpose: "team_membership",
      kind: "user",
      query: debounced,
      teamId,
    },
    { enabled: !disabled },
  );
  const eligible =
    recipients.data?.items.filter(
      (recipient) => !excludedUserIds.includes(recipient.id),
    ) ?? [];

  useEffect(() => {
    if (!allowedRoles.includes(role)) setRole(allowedRoles[0]);
  }, [allowedRoles, role]);

  return (
    <div
      className="space-y-2 rounded-lg border p-3"
      data-testid="team-member-picker"
    >
      <Label htmlFor={inputId}>{t("teams.searchUsers")}</Label>
      <Input
        id={inputId}
        value={search}
        disabled={disabled}
        placeholder={t("teams.searchUsers")}
        aria-describedby={`${inputId}-hint`}
        onChange={(event) => {
          setSearch(event.target.value);
          setSelected(null);
        }}
      />
      <p id={`${inputId}-hint`} className="text-xs text-muted-foreground">
        {t("teams.searchHint")}
      </p>
      {recipients.isFetching && <p role="status">{t("sharing.searching")}</p>}
      {eligible.length > 0 && (
        <ul className="max-h-36 space-y-1 overflow-y-auto">
          {eligible.map((recipient) => (
            <li key={recipient.id}>
              <button
                type="button"
                className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:bg-muted"
                aria-pressed={selected?.id === recipient.id}
                onClick={() => setSelected(recipient)}
              >
                {recipient.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {recipients.data && eligible.length === 0 && debounced.length >= 2 && (
        <p className="text-sm text-muted-foreground">{t("teams.noUsers")}</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={role}
          onValueChange={(value) => setRole(value as TeamRole)}
          disabled={disabled}
        >
          <SelectTrigger className="min-w-36" aria-label={t("teams.role")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {allowedRoles.map((option) => (
              <SelectItem key={option} value={option}>
                {t(`teams.role.${option}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          size="md"
          disabled={!selected || disabled}
          onClick={() => {
            if (!selected) return;
            onAdd(selected, role);
            setSelected(null);
            setSearch("");
          }}
        >
          {t("teams.addMember")}
        </Button>
      </div>
    </div>
  );
}
