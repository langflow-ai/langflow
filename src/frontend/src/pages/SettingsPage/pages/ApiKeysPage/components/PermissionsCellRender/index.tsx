import { useState } from "react";
import { useTranslation } from "react-i18next";
import ApiKeyPermissionsEditor, {
  isApiKeyPermissionPolicyValid,
  normalizeApiKeyPermissionPolicy,
} from "@/components/core/apiKeyPermissionsEditor";
import { Button } from "@/components/ui/button";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import {
  type IApiKeysDataArray,
  useGetApiKeyPermissionOptions,
  usePatchApiKeyPermissions,
} from "@/controllers/API/queries/api-keys";
import BaseModal from "@/modals/baseModal";
import type { ApiKeyPermissionPolicy } from "@/types/api-key-permissions";

export default function PermissionsCellRender({
  data,
}: {
  data: IApiKeysDataArray;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [policy, setPolicy] = useState<ApiKeyPermissionPolicy | null>(null);
  const options = useGetApiKeyPermissionOptions({ enabled: open });
  const mutation = usePatchApiKeyPermissions();
  const persisted = data.permissions
    ? normalizeApiKeyPermissionPolicy(data.permissions)
    : null;
  const restriction =
    persisted?.roles.length === 0 && persisted.restrictions.length === 1
      ? persisted.restrictions[0]
      : null;
  const simpleRestriction =
    restriction &&
    restriction.actions.length > 0 &&
    restriction.actions.length <= 3 &&
    t(`apiKey.permissions.resource.${restriction.resource_type}`) !==
      `apiKey.permissions.resource.${restriction.resource_type}` &&
    restriction.actions.every(
      (action) =>
        t(`apiKey.permissions.action.${action}`) !==
        `apiKey.permissions.action.${action}`,
    );
  const summary = simpleRestriction
    ? t("apiKey.permissions.specificSummary", {
        resource: t(`apiKey.permissions.resource.${restriction.resource_type}`),
        actions: new Intl.ListFormat(i18n.resolvedLanguage ?? i18n.language, {
          style: "short",
          type: "conjunction",
        }).format(
          restriction.actions.map((action) =>
            t(`apiKey.permissions.action.${action}`),
          ),
        ),
        scope: t(`apiKey.permissions.scope.${restriction.domain_type}`),
      })
    : persisted
      ? t("apiKey.permissions.summary", {
          count: persisted.roles.length + persisted.restrictions.length,
        })
      : t("apiKey.permissions.fullAccess");
  const setModalOpen = (next: boolean) => {
    if (next) {
      setPolicy(persisted);
      setError(null);
    }
    setOpen(next);
  };
  const save = () => {
    if (
      !options.data?.supported ||
      options.isError ||
      options.isFetching ||
      !isApiKeyPermissionPolicyValid(policy, options.data)
    )
      return;
    mutation.mutate(
      { id: data.id, permissions: policy },
      {
        onSuccess: () => setOpen(false),
        onError: (failure) =>
          setError(
            extractApiErrorMessage(failure, t("apiKey.permissions.saveError")),
          ),
      },
    );
  };
  return (
    <BaseModal
      open={open}
      setOpen={setModalOpen}
      onSubmit={save}
      size="medium-h-full"
    >
      <BaseModal.Trigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="max-w-full justify-start"
          title={summary}
          aria-label={t("apiKey.permissions.editFor", { name: data.name })}
        >
          <span className="min-w-0 truncate">{summary}</span>
        </Button>
      </BaseModal.Trigger>
      <BaseModal.Header description={t("apiKey.permissions.editDescription")}>
        {t("apiKey.permissions.editTitle", { name: data.name })}
      </BaseModal.Header>
      <BaseModal.Content>
        {options.isError && (
          <p role="alert" className="text-sm text-destructive">
            {t("apiKey.permissions.optionsError")}
          </p>
        )}
        {options.data?.supported && (
          <ApiKeyPermissionsEditor
            options={options.data}
            value={policy}
            onChange={(next) => {
              setPolicy(next);
              setError(null);
            }}
          />
        )}
        {options.data && !options.data.supported && (
          <p role="alert" className="text-sm text-muted-foreground">
            {t("apiKey.permissions.unavailable")}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("apiKey.permissions.save"),
          loading: mutation.isPending,
          disabled:
            !options.data?.supported ||
            options.isFetching ||
            options.isError ||
            mutation.isPending ||
            Boolean(
              options.data &&
                !isApiKeyPermissionPolicyValid(policy, options.data),
            ),
        }}
      />
    </BaseModal>
  );
}
