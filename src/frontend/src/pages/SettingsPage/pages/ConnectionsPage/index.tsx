import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import ConnectionsTable, { ownerKindOf } from "./components/ConnectionsTable";

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

  const connections = connectionsQuery.data ?? [];
  const matches = (connection: ConnectionRead) => {
    const needle = search.trim().toLowerCase();
    if (!needle) return true;
    const account = connection.executing_identity?.account;
    return [
      connection.display_name,
      `${connection.provider_key}/${connection.name}`,
      account?.display ?? "",
      account?.id ?? "",
    ].some((value) => value.toLowerCase().includes(needle));
  };

  const visible = connections.filter((connection) => {
    if (!matches(connection)) return false;
    const owner = ownerKindOf(connection, userData?.id);
    return view === "instance" ? owner === "instance" : owner !== "instance";
  });

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
        list: [
          (error as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ?? t("connections.errors.generic"),
        ],
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

      <Tabs value={view} onValueChange={setView}>
        <TabsList aria-label={t("connections.tabs.label")}>
          <TabsTrigger value="mine">{t("connections.tabs.mine")}</TabsTrigger>
          <TabsTrigger value="instance">
            {t("connections.tabs.instance")}
          </TabsTrigger>
          {extraTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {activeExtra ? (
        activeExtra.render()
      ) : (
        <>
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
              {t("connections.empty")}
            </div>
          ) : (
            <ConnectionsTable
              connections={visible}
              providers={providers}
              currentUserId={userData?.id}
              isSuperuser={isSuperuser}
              busyId={busyId}
              actions={actions}
            />
          )}
        </>
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
        />
      )}
    </div>
  );
}
