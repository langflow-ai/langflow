import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import {
  useDeleteConnectionMutation,
  useEffectiveIntegrationPolicyQuery,
  useGetConnections,
  useIntegrationsQuery,
  useRevokeConnectionMutation,
  useTestConnectionMutation,
  useUpdateConnectionMutation,
} from "@/controllers/API/queries/connections";
import CustomConnectionsTabs from "@/customization/components/custom-connections-tabs";
import SettingsPageHeader from "@/pages/SettingsPage/components/SettingsPageHeader";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import AddConnectionDialog from "./components/AddConnectionDialog";
import ConnectionsTable, {
  type ConnectionsSort,
  ownerKindOf,
} from "./components/ConnectionsTable";

import ManageProvidersPanel from "./components/ManageProvidersPanel";

const EMPTY_CONNECTIONS: ConnectionRead[] = [];

export { default as AddConnectionDialog } from "./components/AddConnectionDialog";
export { default as ConnectionRowMenu } from "./components/ConnectionRowMenu";
export { default as ConnectionStatusBadge } from "./components/ConnectionStatusBadge";
export { ConnectionsTable, ownerKindOf } from "./components/ConnectionsTable";

export default function ConnectionsPage() {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const userData = useAuthStore((state) => state.userData);
  const isSuperuser = Boolean(userData?.is_superuser);

  const [search, setSearch] = useState("");
  const [view, setView] = useState("connections");
  const [ownerFilter, setOwnerFilter] = useState("mine");
  const [sort, setSort] = useState<ConnectionsSort>({
    column: "connection",
    direction: "ascending",
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reauthorizing, setReauthorizing] = useState<
    ConnectionRead | undefined
  >();
  const [busyId, setBusyId] = useState<string | null>(null);

  const connectionsQuery = useGetConnections({});
  const integrationsQuery = useIntegrationsQuery();
  // Read-only here: it tells the page whether a plugin owns integration policy,
  // which the extra tabs need to know before offering to edit it.
  const policyQuery = useEffectiveIntegrationPolicyQuery();

  const test = useTestConnectionMutation();
  const update = useUpdateConnectionMutation();
  const revoke = useRevokeConnectionMutation();
  const remove = useDeleteConnectionMutation();

  const providers = useMemo(
    () =>
      new Map(
        (integrationsQuery.data?.providers ?? []).map((provider) => [
          provider.provider_id,
          provider,
        ]),
      ),
    [integrationsQuery.data],
  );

  const connections = connectionsQuery.data ?? EMPTY_CONNECTIONS;
  // Integration policy can leave nothing to connect; say so rather than open
  // a dialog with an empty provider list.
  const noProviders =
    integrationsQuery.isSuccess &&
    (integrationsQuery.data?.providers ?? []).length === 0;

  // A superuser lists every user's connections, so "not instance-owned" is not
  // the same as "mine" for them: the rest belong to other people and are only
  // visible for administration. Other authorized rows stay under Mine for
  // regular users; ownership alone does not tell us how access was granted.
  const filteredConnections = useMemo(
    () =>
      connections.filter((connection) => {
        const owner = ownerKindOf(connection, userData?.id);
        if (owner === "instance") return ownerFilter === "instance";
        if (owner === "other" && isSuperuser) return ownerFilter === "others";
        return ownerFilter === "mine";
      }),
    [connections, isSuperuser, userData?.id, ownerFilter],
  );
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return filteredConnections;
    return filteredConnections.filter((connection) => {
      const account = connection.executing_identity?.account;
      return [
        connection.display_name,
        `${connection.provider_key}/${connection.name}`,
        account?.display ?? "",
        account?.id ?? "",
      ].some((value) => value.toLowerCase().includes(needle));
    });
  }, [filteredConnections, search]);
  const getEmptyMessage = () => {
    if (connections.length === 0) return t("connections.empty");
    if (filteredConnections.length > 0) return t("connections.noMatches");
    if (ownerFilter === "instance") return t("connections.emptyInstance");
    if (ownerFilter === "others") return t("connections.emptyOthers");
    return t("connections.emptyMine");
  };

  const run = async <T,>(
    connection: ConnectionRead,
    action: () => Promise<T>,
    success: string | ((result: T) => void),
  ) => {
    setBusyId(connection.id);
    try {
      const result = await action();
      if (typeof success === "string") {
        setSuccessData({ title: success });
      } else {
        success(result);
      }
    } catch (error) {
      setErrorData({
        title: t("connections.errors.actionFailed"),
        list: [getAxiosErrorDetail(error, t("connections.errors.generic"))],
      });
    } finally {
      setBusyId(null);
    }
  };

  const actions = {
    onTest: (connection: ConnectionRead) =>
      run(
        connection,
        () => test.mutateAsync({ id: connection.id }),
        t("connections.toast.tested"),
      ),
    onAuthorize: (connection: ConnectionRead) => {
      setReauthorizing(connection);
      setDialogOpen(true);
    },
    onRename: (connection: ConnectionRead) => {
      const next = window.prompt(
        t("connections.actions.rename"),
        connection.display_name,
      );
      if (!next || next.trim() === connection.display_name) return;
      void run(
        connection,
        () =>
          update.mutateAsync({
            id: connection.id,
            patch: { display_name: next.trim() },
          }),
        t("connections.toast.renamed"),
      );
    },
    onToggleUnattended: (connection: ConnectionRead, next: boolean) =>
      run(
        connection,
        () =>
          update.mutateAsync({
            id: connection.id,
            patch: { allow_non_interactive: next },
          }),
        next
          ? t("connections.toast.unattendedOn")
          : t("connections.toast.unattendedOff"),
      ),
    onRevoke: (connection: ConnectionRead) =>
      run(
        connection,
        () => revoke.mutateAsync(connection.id),
        (result) => {
          if (result.provider_revocation === "revoked") {
            setSuccessData({ title: t("connections.toast.revoked") });
          } else {
            setNoticeData({
              title: t(
                result.provider_revocation === "failed"
                  ? "connections.toast.revokeFailed"
                  : "connections.toast.revokedLocally",
              ),
            });
          }
        },
      ),
    onDelete: (connection: ConnectionRead) =>
      run(
        connection,
        () => remove.mutateAsync(connection.id),
        t("connections.toast.deleted"),
      ),
  };

  // Extra tabs (integration policy, for example) come from the distribution.
  const extraTabs = CustomConnectionsTabs({
    isOperator: isSuperuser,
    policyManagedExternally: Boolean(policyQuery.data?.managed_externally),
  }).filter((tab) => !tab.hidden);
  const activeExtra = extraTabs.find((tab) => tab.value === view);

  const connectionsPanel = (
    <div className="flex flex-col gap-6" data-testid="connections-list">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="w-full max-w-sm">
          <Input
            aria-label={t("connections.search")}
            placeholder={t("connections.search")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            data-testid="connections-search"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Label htmlFor="connections-owner-filter">
            {t("connections.filters.owner")}
          </Label>
          <Select value={ownerFilter} onValueChange={setOwnerFilter}>
            <SelectTrigger
              id="connections-owner-filter"
              aria-label={t("connections.filters.owner")}
              className="w-full sm:w-44"
              data-testid="connections-owner-filter"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="mine">
                {t("connections.filters.mine")}
              </SelectItem>
              <SelectItem value="instance">
                {t("connections.filters.instance")}
              </SelectItem>
              {isSuperuser && (
                <SelectItem value="others">
                  {t("connections.filters.others")}
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>
      </div>
      {connectionsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">
          {t("connections.loading")}
        </p>
      ) : visible.length === 0 ? (
        <div
          className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground"
          data-testid="connections-empty"
        >
          {getEmptyMessage()}
        </div>
      ) : (
        <ConnectionsTable
          connections={visible}
          sort={sort}
          onSortChange={setSort}
          providers={providers}
          currentUserId={userData?.id}
          isSuperuser={isSuperuser}
          busyId={busyId}
          actions={actions}
        />
      )}
    </div>
  );

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <SettingsPageHeader
        title={t("connections.title")}
        description={t("connections.subtitle")}
      >
        <Button
          size="sm"
          onClick={() => {
            setReauthorizing(undefined);
            setDialogOpen(true);
          }}
          // Until the provider list has loaded, the dialog would open with
          // no providers and blame policy for a slow or failed request.
          disabled={!integrationsQuery.isSuccess || noProviders}
          data-testid="add-connection"
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          {t("connections.add.title")}
        </Button>
      </SettingsPageHeader>

      {/* Always mounted: a status region inserted with its text already in
          place is not reliably announced. */}
      <p
        className={
          noProviders
            ? "rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground"
            : "sr-only"
        }
        data-testid="connections-no-providers"
        role="status"
      >
        {noProviders ? t("connections.noProviders") : ""}
      </p>

      {isSuperuser || extraTabs.length > 0 ? (
        <Tabs
          value={view}
          onValueChange={setView}
          className="flex w-full flex-col gap-6"
        >
          <TabsList aria-label={t("connections.tabs.label")}>
            <TabsTrigger value="connections">
              {t("connections.tabs.connections")}
            </TabsTrigger>
            {isSuperuser && (
              <TabsTrigger value="providers">
                {t("connections.tabs.providers")}
              </TabsTrigger>
            )}
            {extraTabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="connections" className="mt-0">
            {connectionsPanel}
          </TabsContent>
          {isSuperuser && (
            <TabsContent value="providers" className="mt-0">
              {view === "providers" ? (
                <ManageProvidersPanel
                  providers={integrationsQuery.data?.providers ?? []}
                  deploymentContext={integrationsQuery.data?.deployment_context}
                />
              ) : null}
            </TabsContent>
          )}
          {extraTabs.map((tab) => (
            <TabsContent key={tab.value} value={tab.value} className="mt-0">
              {/* The seam contract says render() only runs for the active tab. */}
              {activeExtra?.value === tab.value ? tab.render() : null}
            </TabsContent>
          ))}
        </Tabs>
      ) : (
        connectionsPanel
      )}

      {dialogOpen && (
        <AddConnectionDialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) setReauthorizing(undefined);
          }}
          providers={integrationsQuery.data?.providers ?? []}
          canCreateInstance={isSuperuser}
          reauthorize={reauthorizing}
          deploymentContext={integrationsQuery.data?.deployment_context}
        />
      )}
    </div>
  );
}
