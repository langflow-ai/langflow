import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import type { ConnectionRead } from "@/controllers/API/queries/connections";

export interface ConnectionStatusBadgeProps {
  connection: ConnectionRead;
  /** Offers the fix inline for the states a user can act on. */
  onAuthorize?: (connection: ConnectionRead) => void;
}

/** The connection's status, plus the one action that resolves it. */
export function ConnectionStatusBadge({
  connection,
  onAuthorize,
}: ConnectionStatusBadgeProps) {
  const { t } = useTranslation();
  const { status } = connection;
  const oauthReason =
    connection.status_reason === "oauth-denied"
      ? t("connections.add.denied")
      : connection.status_reason === "oauth-expired"
        ? t("connections.add.expired")
        : connection.status_reason === "oauth-failed"
          ? t("connections.add.failed")
          : null;

  const action = (label: string) =>
    onAuthorize ? (
      <button
        type="button"
        className="text-xs font-medium underline underline-offset-2 hover:text-primary"
        onClick={() => onAuthorize(connection)}
        data-testid={`authorize-${connection.name}`}
      >
        {label}
      </button>
    ) : null;

  if (status === "ready") {
    return (
      <div className="flex flex-col gap-1">
        <Badge variant="successStatic" size="xq" className="w-fit">
          {t("connections.status.ready")}
        </Badge>
        {oauthReason && (
          <span className="max-w-[16rem] text-xs text-muted-foreground">
            {oauthReason}
          </span>
        )}
      </div>
    );
  }

  if (status === "pending") {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="secondaryStatic" size="xq">
          {t("connections.status.pending")}
        </Badge>
        {action(t("connections.status.authorize"))}
      </div>
    );
  }

  if (status === "expired") {
    return (
      <div className="flex items-center gap-2">
        <Badge
          variant="outline"
          size="xq"
          className="border-accent-amber-foreground text-accent-amber-foreground"
        >
          {t("connections.status.expired")}
        </Badge>
        {action(t("connections.status.reauthorize"))}
      </div>
    );
  }

  if (status === "revoked") {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="secondaryStatic" size="xq">
          {t("connections.status.revoked")}
        </Badge>
        {action(t("connections.status.reauthorize"))}
      </div>
    );
  }

  // `error` carries a reason: the credential is missing, or no longer decrypts
  // with this instance's key. Neither is fixable without re-authorizing.
  const reason =
    connection.status_reason === "credential-missing"
      ? t("connections.status.reasonMissing")
      : connection.status_reason === "credential-undecryptable"
        ? t("connections.status.reasonUndecryptable")
        : oauthReason;

  return (
    <div className="flex flex-col gap-1">
      <Badge variant="errorStatic" size="xq" className="w-fit">
        {t("connections.status.error")}
      </Badge>
      {reason && (
        <span className="max-w-[16rem] text-xs text-muted-foreground">
          {reason}
        </span>
      )}
    </div>
  );
}

export default ConnectionStatusBadge;
