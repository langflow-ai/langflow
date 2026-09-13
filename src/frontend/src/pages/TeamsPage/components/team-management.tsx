import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGetAuthorizationCapabilities } from "@/controllers/API/queries/authorization";
import { useGetTeams } from "@/controllers/API/queries/teams";
import { cn } from "@/utils/utils";
import { TeamCreateDialog } from "./team-create-dialog";
import { TeamDetails } from "./team-details";

export function TeamManagement({
  adminMode,
  layout = "page",
}: {
  adminMode: boolean;
  layout?: "page" | "panel";
}) {
  const { t } = useTranslation();
  const searchId = useId();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const capabilities = useGetAuthorizationCapabilities();
  const ready = Boolean(
    capabilities.data?.enforcement_active &&
      capabilities.data.service_ready &&
      capabilities.data.team_roles_supported,
  );
  const permitted =
    !adminMode || capabilities.data?.can_administer_platform === true;
  const teams = useGetTeams(
    {
      view: adminMode ? "all" : "member",
      search: debouncedSearch || undefined,
      limit: 25,
      offset,
    },
    { enabled: ready && permitted },
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setOffset(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (
      selectedTeamId &&
      teams.data?.some((team) => team.id === selectedTeamId)
    )
      return;
    setSelectedTeamId(teams.data?.[0]?.id ?? null);
  }, [selectedTeamId, teams.data]);

  if (capabilities.isLoading)
    return <p role="status">{t("authz.guard.loading")}</p>;
  if (capabilities.isError || !ready) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{t("authz.guard.unavailable")}</AlertDescription>
      </Alert>
    );
  }
  if (!permitted) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{t("authz.guard.adminRequired")}</AlertDescription>
      </Alert>
    );
  }

  const Container = layout === "panel" ? "section" : "main";
  const Heading = layout === "panel" ? "h3" : "h1";

  return (
    <Container
      className={cn(
        "flex min-h-0 w-full min-w-0 flex-col gap-5",
        layout === "page" && "h-full p-6",
      )}
      data-testid={adminMode ? "admin-teams-page" : "teams-page"}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Heading
            className={cn(
              "font-semibold",
              layout === "panel" ? "text-lg" : "text-2xl",
            )}
          >
            {t(
              layout === "panel"
                ? "authz.navigation.teams"
                : adminMode
                  ? "teams.title.admin"
                  : "teams.title.member",
            )}
          </Heading>
          <p className="mt-1 text-sm text-muted-foreground">
            {t(adminMode ? "teams.subtitle.admin" : "teams.subtitle.member")}
          </p>
        </div>
        {capabilities.data?.can_create_team && (
          <Button type="button" onClick={() => setCreateOpen(true)}>
            {t("teams.create")}
          </Button>
        )}
      </div>
      <div className="grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.7fr)]">
        <section
          className="flex min-h-0 min-w-0 flex-col rounded-xl border bg-background"
          aria-label={t("teams.title.member")}
        >
          <div className="space-y-1.5 border-b p-3">
            <Label htmlFor={searchId}>{t("teams.search")}</Label>
            <Input
              id={searchId}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("teams.search")}
              aria-label={t("teams.search")}
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {teams.isLoading ? (
              <p role="status" className="p-3 text-sm text-muted-foreground">
                {t("teams.loading")}
              </p>
            ) : teams.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{t("teams.error")}</AlertDescription>
              </Alert>
            ) : teams.data?.length ? (
              <ul className="space-y-1">
                {teams.data.map((team) => (
                  <li key={team.id}>
                    <button
                      type="button"
                      className={cn(
                        "w-full rounded-lg p-3 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        selectedTeamId === team.id && "bg-muted",
                      )}
                      aria-pressed={selectedTeamId === team.id}
                      onClick={() => setSelectedTeamId(team.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium">
                          {team.team_name}
                        </span>
                        <Badge
                          variant={
                            team.is_active ? "successStatic" : "secondaryStatic"
                          }
                          size="tag"
                        >
                          {team.is_active
                            ? t("teams.status.active")
                            : t("teams.status.inactive")}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {team.adom_name}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                        <span>
                          {t("teams.memberCount", { count: team.member_count })}
                        </span>
                        <span>
                          {t("teams.activeAdminCount", {
                            count: team.active_admin_count,
                          })}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-3 text-sm text-muted-foreground">
                {t("teams.empty")}
              </p>
            )}
          </div>
          <div className="flex justify-end gap-2 border-t p-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset((current) => Math.max(0, current - 25))}
            >
              {t("teams.previous")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={(teams.data?.length ?? 0) < 25}
              onClick={() => setOffset((current) => current + 25)}
            >
              {t("teams.next")}
            </Button>
          </div>
        </section>
        <section
          className="min-h-0 min-w-0 overflow-y-auto rounded-xl border bg-background p-5"
          aria-live="polite"
        >
          {selectedTeamId ? (
            <TeamDetails
              teamId={selectedTeamId}
              onDeleted={() => setSelectedTeamId(null)}
            />
          ) : (
            <p className="text-sm text-muted-foreground">{t("teams.select")}</p>
          )}
        </section>
      </div>
      <TeamCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={setSelectedTeamId}
      />
    </Container>
  );
}
