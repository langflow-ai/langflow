import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  useDeleteShare,
  useUpdateShare,
} from "@/controllers/API/queries/shares";
import type {
  AuthorizationShare,
  ShareDialogPermission,
  ShareResourceType,
  ShareSummary,
} from "@/types/authz";
import { extractApiErrorMessages } from "@/utils/apiError";
import {
  permissionLabelKey,
  permissionOptions,
  preservedPermissionDescriptionKey,
  preservedPermissionLabelKey,
} from "./permission-options";

function GrantRow({
  grant,
  resourceType,
  resourceId,
}: {
  grant: AuthorizationShare;
  resourceType: ShareResourceType;
  resourceId: string;
}) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const updateShare = useUpdateShare({
    onError: (requestError) =>
      setError(extractApiErrorMessages(requestError).join(" ")),
  });
  const deleteShare = useDeleteShare({
    onError: (requestError) =>
      setError(extractApiErrorMessages(requestError).join(" ")),
  });
  const currentPermission = permissionOptions.includes(
    grant.permission_level as ShareDialogPermission,
  )
    ? (grant.permission_level as ShareDialogPermission)
    : null;
  const preservedPermission =
    grant.permission_level === "read" || grant.permission_level === "admin"
      ? grant.permission_level
      : null;
  const target = grant.target_name ?? t("sharing.unknownRecipient");

  const updatePermission = (value: string) => {
    const permission = value as ShareDialogPermission;
    if (permission === currentPermission) return;
    setError(null);
    updateShare.mutate({
      shareId: grant.id,
      revision: grant.revision,
      resourceType,
      resourceId,
      permission,
    });
  };

  const permissionPicker = (
    <RadioGroup
      className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2"
      value={currentPermission ?? ""}
      aria-label={t(
        currentPermission
          ? "sharing.permission.for"
          : "sharing.convertPermission.for",
        { target },
      )}
      data-testid={`share-grant-permission-${grant.id}`}
      disabled={updateShare.isPending || deleteShare.isPending}
      onValueChange={updatePermission}
    >
      {permissionOptions.map((permission) => (
        <Label
          key={permission}
          className="flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs"
        >
          <RadioGroupItem value={permission} />
          <span>{t(permissionLabelKey(permission))}</span>
        </Label>
      ))}
    </RadioGroup>
  );

  return (
    <li
      className="rounded-lg border border-border p-3"
      data-testid={`share-grant-${grant.id}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{target}</div>
          <Badge variant="secondaryStatic" size="tag" className="mt-1">
            {grant.scope === "team"
              ? t("sharing.recipient.team")
              : t("sharing.recipient.user")}
          </Badge>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-destructive"
          loading={deleteShare.isPending}
          aria-label={t("sharing.revoke.target", { target })}
          onClick={() => {
            setError(null);
            deleteShare.mutate({
              shareId: grant.id,
              revision: grant.revision,
              resourceType,
              resourceId,
            });
          }}
        >
          {t("sharing.remove")}
        </Button>
      </div>
      {currentPermission ? (
        permissionPicker
      ) : preservedPermission ? (
        <>
          <div
            className="mt-3 rounded-md border bg-muted/30 p-2"
            data-testid={`preserved-share-permission-${grant.id}`}
          >
            <div className="text-xs font-medium">
              {t(preservedPermissionLabelKey(preservedPermission))}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {t(preservedPermissionDescriptionKey(preservedPermission))}
            </p>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("sharing.convertPermission")}
          </p>
          {permissionPicker}
        </>
      ) : null}
      {error && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {error}
        </p>
      )}
    </li>
  );
}

export function ExistingAccessSection({
  summary,
  resourceType,
  resourceId,
  grantOffset,
  pageSize,
  isFetching,
  onGrantOffsetChange,
}: {
  summary: ShareSummary;
  resourceType: ShareResourceType;
  resourceId: string;
  grantOffset: number;
  pageSize: number;
  isFetching: boolean;
  onGrantOffsetChange: (offset: number) => void;
}) {
  const { t } = useTranslation();

  return (
    <section
      aria-labelledby="existing-access-heading"
      className="space-y-3 border-t pt-4"
    >
      <h3 id="existing-access-heading" className="text-sm font-semibold">
        {t("sharing.existingAccess")}
      </h3>
      {summary.direct_grants.length ? (
        <ul className="space-y-2">
          {summary.direct_grants.map((grant) => (
            <GrantRow
              key={grant.id}
              grant={grant}
              resourceType={resourceType}
              resourceId={resourceId}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{t("sharing.noGrants")}</p>
      )}
      {(grantOffset > 0 || summary.has_more) && (
        <nav
          className="flex items-center justify-end gap-2"
          aria-label={t("sharing.grantsPagination")}
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={grantOffset === 0 || isFetching}
            onClick={() =>
              onGrantOffsetChange(Math.max(0, grantOffset - pageSize))
            }
          >
            {t("teams.previous")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!summary.has_more || isFetching}
            onClick={() => onGrantOffsetChange(grantOffset + pageSize)}
          >
            {t("teams.next")}
          </Button>
        </nav>
      )}
      {summary.inherited_from_project && (
        <p className="text-xs text-muted-foreground">
          {t("sharing.inheritedAccess")}
        </p>
      )}
      {summary.additional_access_warning && (
        <Alert>
          <AlertDescription>
            {t("sharing.additionalAccessWarning")}
          </AlertDescription>
        </Alert>
      )}
      {summary.legacy_public_access && (
        <Alert>
          <AlertDescription>
            {t("sharing.legacyPublicWarning")}
          </AlertDescription>
        </Alert>
      )}
    </section>
  );
}
