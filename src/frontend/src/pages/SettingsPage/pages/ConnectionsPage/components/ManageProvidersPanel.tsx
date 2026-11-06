import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import type {
  DeploymentContext,
  IntegrationProviderRead,
  SavedOAuthRegistrationRead,
} from "@/controllers/API/queries/connections";
import {
  useDeleteSavedOAuthRegistrationMutation,
  useOAuthRegistrationsQuery,
  useSavedOAuthRegistrationsQuery,
  useSaveOAuthRegistrationMutation,
} from "@/controllers/API/queries/connections";
import useAlertStore from "@/stores/alertStore";
import { callbackUrl } from "../helpers/setup-guide";

const REGISTRATION_ID = /^[a-z0-9][a-z0-9_-]*$/;

/** Providers whose registration is bound to one tenant, with an example value. */
const REQUIRED_TENANT = new Map([
  ["microsoft", "00000000-0000-0000-0000-000000000000"],
  ["servicenow", "https://<instance>.service-now.com"],
]);

const STATUS_KEYS = {
  active: "connections.providers.status.active",
  pending: "connections.providers.status.pending",
  removed: "connections.providers.status.removed",
  overridden: "connections.providers.status.overridden",
} as const;

/** Changes the running server applied, which processes started earlier pick up on restart. */
const RESTART_HINTS: Partial<
  Record<SavedOAuthRegistrationRead["status"], string>
> = {
  pending: "connections.providers.statusHint.pending",
  removed: "connections.providers.statusHint.removed",
};

type ClientType = "confidential" | "public";

interface ProviderForm {
  provider: string;
  id: string;
  /** The administrator typed the ID, so a provider change keeps it. */
  idEdited: boolean;
  clientId: string;
  clientSecret: string;
  clientType: ClientType;
  redirectUri: string;
  tenant: string;
  scopes: string;
  /** Replacing a saved registration: a blank secret keeps the saved one. */
  replacing: boolean;
  registration?: Record<string, unknown>;
}

/** OAuth profiles are the ones a provider does not list as manual-token profiles. */
function oauthProfile(provider: IntegrationProviderRead): string | undefined {
  const manual = new Set(
    (provider.manual_token_profiles ?? []).map((profile) => profile.id),
  );
  return provider.capabilities
    .map((capability) => capability.auth_profile_id)
    .find((profile) => !manual.has(profile));
}

function providerScopes(provider: IntegrationProviderRead, profile: string) {
  const scopes = provider.capabilities
    .filter((capability) => capability.auth_profile_id === profile)
    .flatMap((capability) => capability.required_scopes ?? []);
  return [...new Set(scopes)].join(", ");
}

function defaultRegistrationId(providerId: string, taken: Set<string>) {
  const base = `${providerId}-work`;
  let id = base;
  for (let n = 2; taken.has(id); n += 1) id = `${base}-${n}`;
  return id;
}

function emptyForm(
  provider: IntegrationProviderRead | undefined,
  taken: Set<string>,
): ProviderForm {
  const providerId = provider?.provider_id ?? "";
  const profile = provider ? oauthProfile(provider) : undefined;
  return {
    provider: providerId,
    id: providerId ? defaultRegistrationId(providerId, taken) : "",
    idEdited: false,
    clientId: "",
    clientSecret: "",
    clientType: "confidential",
    redirectUri: providerId
      ? (callbackUrl(providerId, window.location.origin) ?? "")
      : "",
    tenant: "",
    scopes: provider && profile ? providerScopes(provider, profile) : "",
    replacing: false,
  };
}

const text = (value: unknown) => (typeof value === "string" ? value : "");

function savedForm(saved: SavedOAuthRegistrationRead): ProviderForm {
  const registration = saved.registration;
  const scopes = Array.isArray(registration.scopes) ? registration.scopes : [];
  return {
    provider: text(registration.provider),
    id: saved.id,
    idEdited: true,
    clientId: text(registration.client_id),
    clientSecret: "",
    clientType:
      registration.client_type === "public" ? "public" : "confidential",
    redirectUri: text(registration.redirect_uri),
    tenant: text(registration.tenant),
    scopes: scopes.filter((scope) => typeof scope === "string").join(", "),
    replacing: true,
    registration,
  };
}

function RowStatus({
  status,
}: {
  status: SavedOAuthRegistrationRead["status"];
}) {
  const { t } = useTranslation();
  const hint = RESTART_HINTS[status];
  if (!hint) return <>{t(STATUS_KEYS[status])}</>;
  return (
    <ShadTooltip content={t(hint)}>
      <span
        tabIndex={0}
        className="inline-flex items-center gap-1.5 text-accent-amber-foreground"
      >
        {t(STATUS_KEYS[status])}
        <ForwardedIconComponent name="Info" className="h-3.5 w-3.5 shrink-0" />
      </span>
    </ShadTooltip>
  );
}

export default function ManageProvidersPanel({
  providers,
  deploymentContext = "self_managed",
}: {
  providers: IntegrationProviderRead[];
  deploymentContext?: DeploymentContext;
}) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const oauthProviders = useMemo(
    () => providers.filter((provider) => oauthProfile(provider)),
    [providers],
  );
  const savedQuery = useSavedOAuthRegistrationsQuery();
  const activeQuery = useOAuthRegistrationsQuery(undefined);
  const saveRegistration = useSaveOAuthRegistrationMutation();
  const deleteRegistration = useDeleteSavedOAuthRegistrationMutation();

  const [form, setForm] = useState<ProviderForm | null>(null);
  const [saving, setSaving] = useState(false);
  const loading = savedQuery.isLoading || activeQuery.isLoading;
  const loadFailed = savedQuery.isError || activeQuery.isError;

  // Saved registrations are shared by every superuser; the active list is what
  // the running server uses, so an active ID nobody saved comes from its environment.
  const rows = useMemo(() => {
    const saved = new Map(
      (savedQuery.data ?? []).map((entry) => [entry.id, entry]),
    );
    const active = new Map(
      (activeQuery.data ?? []).map((registration) => [
        registration.id,
        registration,
      ]),
    );
    const ids = [...new Set([...saved.keys(), ...active.keys()])].sort();
    return ids.map((id) => ({
      id,
      saved: saved.get(id),
      provider:
        active.get(id)?.provider ?? text(saved.get(id)?.registration.provider),
    }));
  }, [savedQuery.data, activeQuery.data]);
  const takenIds = useMemo(() => new Set(rows.map((row) => row.id)), [rows]);

  const providerName = (providerId: string) =>
    oauthProviders.find((item) => item.provider_id === providerId)
      ?.display_name ?? providerId;

  const update = (patch: Partial<ProviderForm>) =>
    setForm((current) => (current ? { ...current, ...patch } : current));

  const formError = (current: ProviderForm) => {
    if (!current.provider || !REGISTRATION_ID.test(current.id))
      return t("connections.providers.errors.id");
    if (!current.replacing && takenIds.has(current.id))
      return t("connections.providers.errors.idTaken", { id: current.id });
    if (!current.clientId.trim() || !current.redirectUri.trim())
      return t("connections.providers.errors.required");
    if (
      current.clientType === "confidential" &&
      !current.clientSecret &&
      !current.replacing
    )
      return t("connections.providers.errors.secret");
    const tenantExample = REQUIRED_TENANT.get(current.provider);
    if (tenantExample && !current.tenant.trim())
      return t("connections.providers.errors.tenant", {
        provider: providerName(current.provider),
        example: tenantExample,
      });
    return null;
  };

  const save = async () => {
    if (!form || loading || loadFailed || saving) return;
    const problem = formError(form);
    if (problem) {
      setErrorData({ title: problem });
      return;
    }
    const provider = oauthProviders.find(
      (item) => item.provider_id === form.provider,
    );
    // An instance URL is compared exactly, so a trailing slash would not match.
    const tenant = form.tenant.trim().replace(/\/+$/, "");
    const previousTenant = text(form.registration?.tenant).replace(/\/+$/, "");
    // The same shape the server reads from LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS.
    const registration = {
      ...(form.registration ?? {
        profile: provider ? oauthProfile(provider) : "user",
        owner: deploymentContext === "hosted" ? "langflow" : "customer",
        context: deploymentContext,
      }),
      provider: form.provider,
      client_type: form.clientType,
      client_id: form.clientId.trim(),
      ...(form.registration?.client_type === "confidential" &&
      form.clientType === "public"
        ? {
            client_secret: null,
            private_key: null,
            certificate_thumbprint: null,
          }
        : {}),
      ...(form.clientSecret && form.registration?.certificate_thumbprint
        ? { private_key: null, certificate_thumbprint: null }
        : {}),
      ...(form.clientSecret ? { client_secret: form.clientSecret } : {}),
      redirect_uri: form.redirectUri.trim(),
      tenant: tenant || null,
      allowed_tenants:
        form.registration && tenant === previousTenant
          ? (form.registration.allowed_tenants ?? [])
          : tenant
            ? [tenant]
            : [],
      scopes: form.scopes
        .split(",")
        .map((scope) => scope.trim())
        .filter(Boolean),
    };
    setSaving(true);
    try {
      await saveRegistration.mutateAsync({ id: form.id, registration });
      setSuccessData({ title: t("connections.providers.toast.saved") });
      setForm(null);
    } catch (error) {
      setErrorData({
        title: t("connections.providers.errors.saveFailed"),
        list: [getAxiosErrorDetail(error, t("connections.errors.generic"))],
      });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteRegistration.mutateAsync(id);
      setSuccessData({ title: t("connections.providers.toast.removed") });
    } catch (error) {
      setErrorData({
        title: t("connections.errors.actionFailed"),
        list: [getAxiosErrorDetail(error, t("connections.errors.generic"))],
      });
    }
  };

  const tenantExample = form ? REQUIRED_TENANT.get(form.provider) : undefined;

  return (
    <div className="flex flex-col gap-6 pb-10" data-testid="manage-providers">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("connections.providers.intro")}
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setForm(emptyForm(oauthProviders[0], takenIds))}
          disabled={oauthProviders.length === 0 || loading || loadFailed}
          data-testid="manage-providers-add"
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          {t("connections.providers.add")}
        </Button>
      </div>

      <Dialog
        open={form !== null}
        onOpenChange={(open) => (open ? null : setForm(null))}
      >
        <DialogContent className="max-h-[calc(100dvh-2rem)] sm:max-w-[640px]">
          <DialogHeader className="shrink-0">
            <DialogTitle>
              {form?.replacing
                ? t("connections.providers.replaceTitle", { id: form.id })
                : t("connections.providers.add")}
            </DialogTitle>
          </DialogHeader>
          {form && (
            <div
              className="flex min-h-0 flex-col gap-4"
              data-testid="manage-providers-form"
            >
              <div className="grid min-h-0 gap-4 overflow-y-auto md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-provider">
                    {t("connections.providers.form.provider")}
                  </Label>
                  <select
                    id="provider-config-provider"
                    className="h-9 rounded-md border border-control bg-background px-2 text-sm"
                    value={form.provider}
                    disabled={form.replacing}
                    onChange={(event) => {
                      const next = emptyForm(
                        oauthProviders.find(
                          (item) => item.provider_id === event.target.value,
                        ),
                        takenIds,
                      );
                      setForm(
                        form.idEdited
                          ? { ...next, id: form.id, idEdited: true }
                          : next,
                      );
                    }}
                  >
                    {oauthProviders.map((provider) => (
                      <option
                        key={provider.provider_id}
                        value={provider.provider_id}
                      >
                        {provider.display_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-id">
                    {t("connections.providers.form.id")}
                  </Label>
                  <Input
                    id="provider-config-id"
                    value={form.id}
                    disabled={form.replacing}
                    onChange={(event) =>
                      update({ id: event.target.value, idEdited: true })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-client-id">
                    {t("connections.providers.form.clientId")}
                  </Label>
                  <Input
                    id="provider-config-client-id"
                    value={form.clientId}
                    onChange={(event) =>
                      update({ clientId: event.target.value })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-client-secret">
                    {t("connections.providers.form.clientSecret")}
                  </Label>
                  <Input
                    id="provider-config-client-secret"
                    type="password"
                    autoComplete="new-password"
                    placeholder={
                      form.replacing
                        ? t("connections.providers.form.secretKeep")
                        : undefined
                    }
                    value={form.clientSecret}
                    onChange={(event) =>
                      update({ clientSecret: event.target.value })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-client-type">
                    {t("connections.providers.form.clientType")}
                  </Label>
                  <select
                    id="provider-config-client-type"
                    className="h-9 rounded-md border border-control bg-background px-2 text-sm"
                    value={form.clientType}
                    onChange={(event) =>
                      update({ clientType: event.target.value as ClientType })
                    }
                  >
                    <option value="confidential">
                      {t("connections.providers.form.confidential")}
                    </option>
                    <option value="public">
                      {t("connections.providers.form.public")}
                    </option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="provider-config-tenant">
                    {tenantExample
                      ? t("connections.providers.form.tenantRequired")
                      : t("connections.providers.form.tenant")}
                  </Label>
                  <Input
                    id="provider-config-tenant"
                    placeholder={tenantExample}
                    value={form.tenant}
                    onChange={(event) => update({ tenant: event.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1.5 md:col-span-2">
                  <Label htmlFor="provider-config-redirect">
                    {t("connections.providers.form.redirectUri")}
                  </Label>
                  <Input
                    id="provider-config-redirect"
                    value={form.redirectUri}
                    onChange={(event) =>
                      update({ redirectUri: event.target.value })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5 md:col-span-2">
                  <Label htmlFor="provider-config-scopes">
                    {t("connections.providers.form.scopes")}
                  </Label>
                  <Input
                    id="provider-config-scopes"
                    value={form.scopes}
                    onChange={(event) => update({ scopes: event.target.value })}
                  />
                </div>
              </div>
              <div className="flex shrink-0 items-center justify-end gap-2">
                <ShadTooltip
                  content={t("connections.providers.form.restartHint")}
                >
                  <span
                    tabIndex={0}
                    className="mr-auto flex items-center gap-1.5 text-xs text-muted-foreground"
                    data-testid="manage-providers-restart-note"
                  >
                    <ForwardedIconComponent
                      name="Info"
                      className="h-3.5 w-3.5 shrink-0"
                    />
                    {t("connections.providers.form.restartNote")}
                  </span>
                </ShadTooltip>
                <Button variant="ghost" onClick={() => setForm(null)}>
                  {t("connections.add.cancel")}
                </Button>
                <Button
                  onClick={save}
                  loading={saving}
                  data-testid="manage-providers-save"
                >
                  {t("connections.providers.form.save")}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {loadFailed ? (
        <p role="alert" className="text-sm text-destructive">
          {t("connections.providers.errors.loadFailed")}
        </p>
      ) : loading ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("loading.loading")}
        </p>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          {t("connections.providers.empty")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr className="border-b">
                <th className="px-4 py-2 font-medium">
                  {t("connections.providers.form.id")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("connections.providers.form.provider")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("connections.columns.status")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("connections.providers.savedBy")}
                </th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono">{row.id}</td>
                  <td className="px-4 py-2">{row.provider || "-"}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    <RowStatus status={row.saved?.status ?? "active"} />
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {row.saved?.saved_by ??
                      t("connections.providers.environment")}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {row.saved && row.saved.status !== "removed" && (
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            row.saved && setForm(savedForm(row.saved))
                          }
                        >
                          {t("connections.providers.replace")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => remove(row.id)}
                        >
                          {t("connections.providers.remove")}
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
