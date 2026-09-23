import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import AddConnectionDialog from "./components/AddConnectionDialog";
import ConnectionsTable, {
  type ConnectionsSort,
  ownerKindOf,
} from "./components/ConnectionsTable";

const EMPTY_CONNECTIONS: ConnectionRead[] = [];

export { default as AddConnectionDialog } from "./components/AddConnectionDialog";
export { default as ConnectionRowMenu } from "./components/ConnectionRowMenu";
export { default as ConnectionStatusBadge } from "./components/ConnectionStatusBadge";
export { ConnectionsTable, ownerKindOf } from "./components/ConnectionsTable";

export default function ConnectionsPage() {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const userData = useAuthStore((state) => state.userData);
  const isSuperuser = Boolean(userData?.is_superuser);

  const [search, setSearch] = useState("");
  const [view, setView] = useState("mine");
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

  // A superuser lists every user's connections, so "not instance-owned" is not
  // the same as "mine" for them: the rest belong to other people and are only
  // visible for administration. Other authorized rows stay under Mine for
  // regular users; ownership alone does not tell us how access was granted.
  const tabConnections = useMemo(
    () =>
      connections.filter((connection) => {
        const owner = ownerKindOf(connection, userData?.id);
        if (owner === "instance") return view === "instance";
        if (owner === "other" && isSuperuser) return view === "others";
        return view === "mine";
      }),
    [connections, isSuperuser, userData?.id, view],
  );
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return tabConnections;
    return tabConnections.filter((connection) => {
      const account = connection.executing_identity?.account;
      return [
        connection.display_name,
        `${connection.provider_key}/${connection.name}`,
        account?.display ?? "",
        account?.id ?? "",
      ].some((value) => value.toLowerCase().includes(needle));
    });
  }, [tabConnections, search]);
  const getEmptyMessage = () => {
    if (connections.length === 0) return t("connections.empty");
    if (tabConnections.length > 0) return t("connections.noMatches");
    if (view === "instance") return t("connections.emptyInstance");
    if (view === "others") return t("connections.emptyOthers");
    return t("connections.emptyTab");
  };

  const run = async (
    connection: ConnectionRead,
    action: () => Promise<unknown>,
    success: string,
  ) => {
    setBusyId(connection.id);
    try {
      await action();
      setSuccessData({ title: success });
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
        t("connections.toast.revoked"),
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

  // One panel body for every built-in tab: `visible` is already filtered by
  // `view`, and Radix only renders the children of the selected TabsContent.
  const connectionsPanel = (
    <div className="flex flex-col gap-6">
      <Input
        placeholder={t("connections.search")}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="max-w-sm"
        data-testid="connections-search"
      />
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
      <div className="flex w-full items-start justify-between gap-4">
        <div className="flex flex-col">
          <h2 className="text-lg font-semibold">{t("connections.title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("connections.subtitle")}
          </p>
        </div>
        <Button
          onClick={() => {
            setReauthorizing(undefined);
            setDialogOpen(true);
          }}
          data-testid="add-connection"
        >
          <ForwardedIconComponent name="Plus" className="mr-2 h-4 w-4" />
          {t("connections.add.title")}
        </Button>
      </div>

      {/*
        Every trigger needs a TabsContent with the matching value: Radix points
        each trigger's aria-controls at the panel id it derives from that value,
        so a panel the page never mounts leaves the reference dangling.

        Radix keeps the unselected panels mounted and marks them `hidden`, so no
        `display` utility may sit on TabsContent itself - a class beats the
        `[hidden] { display: none }` UA rule and would put an empty panel back
        into the layout and the accessibility tree. Panel bodies bring their own
        wrapper instead.
      */}
      <Tabs
        value={view}
        onValueChange={setView}
        className="flex w-full flex-col gap-6"
      >
        <TabsList aria-label={t("connections.tabs.label")}>
          <TabsTrigger value="mine">{t("connections.tabs.mine")}</TabsTrigger>
          <TabsTrigger value="instance">
            {t("connections.tabs.instance")}
          </TabsTrigger>
          {isSuperuser && (
            <TabsTrigger value="others">
              {t("connections.tabs.others")}
            </TabsTrigger>
          )}
          {extraTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="mine" className="mt-0">
          {connectionsPanel}
        </TabsContent>
        <TabsContent value="instance" className="mt-0">
          {connectionsPanel}
        </TabsContent>
        {isSuperuser && (
          <TabsContent value="others" className="mt-0">
            {connectionsPanel}
          </TabsContent>
        )}
        {extraTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value} className="mt-0">
            {/* The seam contract says render() only runs for the active tab. */}
            {activeExtra?.value === tab.value ? tab.render() : null}
          </TabsContent>
        ))}
      </Tabs>

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
        />
      )}
    </div>
  );
}
