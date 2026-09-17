import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CONNECTION_NAME_MAX_LENGTH,
  CONNECTION_NAME_PATTERN,
  type ConnectionPollBaseline,
  type ConnectionRead,
  hasConsentLanded,
  type IntegrationIdentity,
  type IntegrationProviderRead,
  useCreateConnectionMutation,
  useDeleteConnectionMutation,
  useOAuthRegistrationsQuery,
  usePendingConnectionPoll,
  useStartOAuthMutation,
} from "@/controllers/API/queries/connections";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import {
  openAuthorizationUrl,
  resolveRegistrationId,
} from "@/customization/components/custom-connection-authorization";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import {
  partitionByCeiling,
  scopeRequirements,
  shortScope,
  uniqueScopes,
} from "../helpers/scopes";

/** Consent can take a while; stop waiting rather than polling forever. */
const CONSENT_TIMEOUT_MS = 10 * 60 * 1000;

type Step = "details" | "authorize";

type AuthorizeState =
  | { kind: "waiting" }
  | { kind: "connected"; connection: ConnectionRead }
  | { kind: "failed"; message: string };

export interface AddConnectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providers: IntegrationProviderRead[];
  /** Superusers may create connections the whole instance shares. */
  canCreateInstance: boolean;
  /** Re-authorizing an existing connection instead of creating one. */
  reauthorize?: ConnectionRead;
}

export function AddConnectionDialog({
  open,
  onOpenChange,
  providers,
  canCreateInstance,
  reauthorize,
}: AddConnectionDialogProps) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const typesData = useTypesStore((state) => state.data);
  useGetTypes({ enabled: open });

  const [step, setStep] = useState<Step>(reauthorize ? "authorize" : "details");
  const [providerId, setProviderId] = useState(
    reauthorize?.provider_key ?? providers[0]?.provider_id ?? "",
  );
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [identity, setIdentity] = useState<IntegrationIdentity>(
    reauthorize?.executing_identity?.identity ?? "user_delegated",
  );
  const [ownership, setOwnership] = useState<"user" | "instance">("user");
  const [selectedScopes, setSelectedScopes] = useState<Set<string>>(new Set());
  const [registrationId, setRegistrationId] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [authorize, setAuthorize] = useState<AuthorizeState | null>(null);
  const [baseline, setBaseline] = useState<ConnectionPollBaseline | null>(null);
  const [pendingRow, setPendingRow] = useState<ConnectionRead | null>(null);
  const popupRef = useRef<Window | null>(null);
  const startedAt = useRef(0);

  const provider = providers.find((item) => item.provider_id === providerId);
  const create = useCreateConnectionMutation();
  const startOAuth = useStartOAuthMutation();
  const remove = useDeleteConnectionMutation();
  const poll = usePendingConnectionPoll(
    authorize?.kind === "waiting" ? baseline : null,
  );

  const registrations = useOAuthRegistrationsQuery(providerId, open);
  const candidates = useMemo(
    () =>
      (registrations.data ?? []).filter(
        (registration) =>
          registration.provider === providerId &&
          registration.profile === (identity === "bot" ? "bot" : "user"),
      ),
    [registrations.data, providerId, identity],
  );
  const resolvedRegistration = resolveRegistrationId({
    provider: providerId,
    identity,
    registrations: registrations.data ?? null,
    preferredId: registrationId,
  });
  // A listed backend that offers nothing for this provider cannot start consent.
  const noRegistration =
    registrations.data !== null &&
    registrations.isSuccess &&
    resolvedRegistration === null;

  const identities = useMemo<IntegrationIdentity[]>(
    () => [
      ...new Set(
        (provider?.capabilities ?? []).map((capability) => capability.identity),
      ),
    ],
    [provider],
  );

  useEffect(() => {
    if (reauthorize || identities.length === 0) return;
    setIdentity((current) =>
      identities.includes(current) ? current : identities[0],
    );
  }, [identities, reauthorize]);

  const requirements = useMemo(
    () => scopeRequirements(provider?.capabilities ?? [], typesData),
    [provider, typesData],
  );
  const ceiling = candidates.find(
    ({ id }) => id === resolvedRegistration,
  )?.scopes;
  const { requestable, unavailable } = useMemo(
    () => partitionByCeiling(uniqueScopes(requirements), ceiling),
    [requirements, ceiling],
  );

  useEffect(() => {
    if (!provider || reauthorize) return;
    setSelectedScopes(new Set(requestable));
  }, [provider, reauthorize, requestable]);

  // Consent lands on the server: only a row that moved on from the state it had
  // when consent started carries this authorization's outcome.
  useEffect(() => {
    if (authorize?.kind !== "waiting") return;
    if (hasConsentLanded(poll.data, baseline)) {
      const row = poll.data as ConnectionRead;
      setAuthorize(
        row.status === "ready" && row.has_credentials
          ? { kind: "connected", connection: row }
          : { kind: "failed", message: t("connections.add.failed") },
      );
      return;
    }
    if (Date.now() - startedAt.current > CONSENT_TIMEOUT_MS) {
      setAuthorize({ kind: "failed", message: t("connections.add.expired") });
    }
  }, [authorize, poll.data, baseline, t]);

  // The window closing without a change is a cancellation, not a failure to retry.
  useEffect(() => {
    if (authorize?.kind !== "waiting") return;
    const timer = window.setInterval(() => {
      if (popupRef.current?.closed && !hasConsentLanded(poll.data, baseline)) {
        setAuthorize({
          kind: "failed",
          message: t("connections.add.cancelled"),
        });
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [authorize, poll.data, baseline, t]);

  const beginAuthorize = useCallback(
    async (connection: ConnectionRead, scopes: string[]) => {
      const registration = resolveRegistrationId({
        provider: connection.provider_key,
        identity: connection.executing_identity?.identity ?? "user_delegated",
        registrations: registrations.data ?? null,
        preferredId: registrationId,
      });
      if (!registration) {
        setAuthorize({
          kind: "failed",
          message: t("connections.add.noRegistration"),
        });
        return;
      }
      startedAt.current = Date.now();
      setStep("authorize");
      setAuthorize({ kind: "waiting" });
      setPendingRow(connection);
      // oauth/start does not touch the row, so this is still the pre-consent state.
      setBaseline({ id: connection.id, updatedAt: connection.updated_at });
      try {
        const { authorization_url } = await startOAuth.mutateAsync({
          id: connection.id,
          registrationId: registration,
          scopes,
        });
        popupRef.current = openAuthorizationUrl(
          authorization_url,
          popupRef.current,
        );
      } catch {
        popupRef.current?.close();
        setAuthorize({ kind: "failed", message: t("connections.add.failed") });
      }
    },
    [registrations.data, registrationId, startOAuth, t],
  );

  // Re-authorizing skips the details step: the handle and identity already exist.
  useEffect(() => {
    if (!open || !reauthorize || authorize) return;
    void beginAuthorize(
      reauthorize,
      reauthorize.granted_scopes.length > 0
        ? reauthorize.granted_scopes
        : requestable,
    );
  }, [open, reauthorize, authorize, beginAuthorize, requestable]);

  const handleValid =
    CONNECTION_NAME_PATTERN.test(name) &&
    name.length <= CONNECTION_NAME_MAX_LENGTH;
  const canContinue =
    !!provider &&
    handleValid &&
    displayName.trim().length > 0 &&
    !noRegistration;

  const onContinue = async () => {
    if (!provider || !canContinue) return;
    setFieldError(null);
    // Open on the click itself so popup blockers treat it as user-initiated.
    popupRef.current = window.open(
      "about:blank",
      "langflow-oauth-consent",
      "width=520,height=700",
    );
    try {
      const row = await create.mutateAsync({
        provider_key: provider.provider_id,
        name,
        display_name: displayName.trim(),
        ownership_mode: ownership,
        executing_identity: { identity },
      });
      await beginAuthorize(row, [...selectedScopes]);
    } catch (error) {
      popupRef.current?.close();
      setFieldError(
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? t("connections.add.failed"),
      );
    }
  };

  const close = (discardPending: boolean) => {
    const row = pendingRow;
    if (
      discardPending &&
      row &&
      !reauthorize &&
      authorize?.kind !== "connected"
    ) {
      remove.mutate(row.id, {
        // The dialog is already closing, so say it rather than leaving a
        // half-made connection behind with no explanation.
        onError: () =>
          setErrorData({
            title: t("connections.add.cleanupFailed"),
            list: [t("connections.add.cleanupFailedBody")],
          }),
      });
    }
    popupRef.current?.close();
    setStep(reauthorize ? "authorize" : "details");
    setAuthorize(null);
    setBaseline(null);
    setPendingRow(null);
    setName("");
    setDisplayName("");
    setFieldError(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? null : close(true))}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>
            {reauthorize
              ? t("connections.add.reauthorizeTitle", {
                  name: reauthorize.display_name,
                })
              : t("connections.add.title")}
          </DialogTitle>
        </DialogHeader>

        {step === "details" && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connection-provider">
                {t("connections.add.provider")}
              </Label>
              <select
                id="connection-provider"
                className="h-9 rounded-md border border-border bg-background px-2 text-sm"
                value={providerId}
                onChange={(event) => setProviderId(event.target.value)}
                data-testid="connection-provider"
              >
                {providers.map((item) => (
                  <option key={item.provider_id} value={item.provider_id}>
                    {item.display_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="connection-name">
                  {t("connections.add.handle")}
                </Label>
                <Input
                  id="connection-name"
                  value={name}
                  spellCheck={false}
                  placeholder="work"
                  onChange={(event) =>
                    setName(
                      event.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9_-]/g, ""),
                    )
                  }
                  data-testid="connection-name"
                />
                <span className="font-mono text-xs text-muted-foreground">
                  {providerId}/{name || "…"}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="connection-display-name">
                  {t("connections.add.displayName")}
                </Label>
                <Input
                  id="connection-display-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  data-testid="connection-display-name"
                />
              </div>
            </div>

            {identities.length > 1 && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="connection-identity">
                  {t("connections.add.identity")}
                </Label>
                <select
                  id="connection-identity"
                  className="h-9 rounded-md border border-border bg-background px-2 text-sm"
                  value={identity}
                  onChange={(event) =>
                    setIdentity(event.target.value as IntegrationIdentity)
                  }
                  data-testid="connection-identity"
                >
                  {identities.map((option) => (
                    <option key={option} value={option}>
                      {t(`connections.identity.${option}`)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {candidates.length > 1 && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="connection-registration">
                  {t("connections.add.registration")}
                </Label>
                <select
                  id="connection-registration"
                  className="h-9 rounded-md border border-border bg-background px-2 text-sm"
                  value={resolvedRegistration ?? ""}
                  onChange={(event) => setRegistrationId(event.target.value)}
                >
                  {candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.id}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {canCreateInstance && (
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={ownership === "instance"}
                  onCheckedChange={(checked) =>
                    setOwnership(checked ? "instance" : "user")
                  }
                  data-testid="connection-instance-owned"
                />
                {t("connections.add.instanceOwned")}
              </label>
            )}

            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium">
                {t("connections.add.scopes")}
              </span>
              {requestable.length === 0 && (
                <span className="text-xs text-muted-foreground">
                  {t("connections.add.noScopes")}
                </span>
              )}
              <div className="flex flex-col gap-1.5">
                {requestable.map((scope) => (
                  <label
                    key={scope}
                    className="flex items-center gap-2 font-mono text-xs"
                  >
                    <Checkbox
                      checked={selectedScopes.has(scope)}
                      onCheckedChange={(checked) =>
                        setSelectedScopes((current) => {
                          const next = new Set(current);
                          if (checked) next.add(scope);
                          else next.delete(scope);
                          return next;
                        })
                      }
                    />
                    {shortScope(scope)}
                  </label>
                ))}
              </div>
              {unavailable.length > 0 && (
                <span className="text-xs text-warning-foreground">
                  {t("connections.add.scopesOutsideCeiling", {
                    scopes: unavailable.map(shortScope).join(", "),
                  })}
                </span>
              )}
            </div>

            {noRegistration && (
              <p className="text-xs text-destructive" role="alert">
                {t("connections.add.noRegistration")}
              </p>
            )}
            {fieldError && (
              <p className="text-xs text-destructive" role="alert">
                {fieldError}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => close(true)}>
                {t("connections.add.cancel")}
              </Button>
              <Button
                disabled={!canContinue || create.isPending}
                onClick={onContinue}
                data-testid="connection-continue"
              >
                {t("connections.add.continue")}
              </Button>
            </div>
          </div>
        )}

        {step === "authorize" && (
          <div className="flex flex-col gap-4">
            {authorize?.kind === "waiting" && (
              <div className="flex items-center gap-3 text-sm">
                <ForwardedIconComponent
                  name="Loader2"
                  className="h-4 w-4 animate-spin"
                />
                {t("connections.add.waiting")}
              </div>
            )}
            {authorize?.kind === "connected" && (
              <div className="flex flex-col gap-2 text-sm">
                <span className="flex items-center gap-2 font-medium">
                  <ForwardedIconComponent
                    name="CircleCheckBig"
                    className="h-4 w-4 text-accent-emerald-foreground"
                  />
                  {t("connections.add.connected")}
                </span>
                <div className="flex flex-wrap gap-1">
                  {authorize.connection.granted_scopes.map((scope) => (
                    <Badge key={scope} variant="secondaryStatic" size="xq">
                      {shortScope(scope)}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {authorize?.kind === "failed" && (
              <p className="text-sm text-destructive" role="alert">
                {authorize.message}
              </p>
            )}
            <div className="flex justify-end gap-2">
              {authorize?.kind === "failed" && pendingRow && (
                <Button
                  variant="outline"
                  onClick={() =>
                    beginAuthorize(
                      poll.data ?? pendingRow,
                      reauthorize?.granted_scopes.length
                        ? reauthorize.granted_scopes
                        : [...selectedScopes],
                    )
                  }
                >
                  {t("connections.add.tryAgain")}
                </Button>
              )}
              <Button
                onClick={() => close(authorize?.kind !== "connected")}
                data-testid="connection-done"
              >
                {authorize?.kind === "connected"
                  ? t("connections.add.done")
                  : t("connections.add.cancel")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default AddConnectionDialog;
