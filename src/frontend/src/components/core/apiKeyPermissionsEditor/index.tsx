import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGetApiKeyPermissionTargets } from "@/controllers/API/queries/api-keys/use-get-api-key-permission-targets";
import type {
  ApiKeyPermissionOptions,
  ApiKeyPermissionPolicy,
  ApiKeyPermissionScope,
  ApiKeyResourceRestriction,
  ApiKeyScopeType,
} from "@/types/api-key-permissions";
import { emptyApiKeyPermissionPolicy } from "@/types/api-key-permissions";

const selectClass =
  "min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
const ALL_SCOPES: ApiKeyScopeType[] = ["global", "workspace", "project"];

export function normalizeApiKeyPermissionPolicy(
  value: ApiKeyPermissionPolicy,
): ApiKeyPermissionPolicy {
  return {
    ...value,
    roles: (value.roles ?? []).map((role) => ({
      ...role,
      domain_type: role.domain_type ?? "global",
      domain_id: role.domain_id ?? null,
    })),
    restrictions: (value.restrictions ?? []).map((restriction) => ({
      ...restriction,
      domain_type: restriction.domain_type ?? "global",
      domain_id: restriction.domain_id ?? null,
      resource_ids: restriction.resource_ids ?? null,
    })),
  };
}

export function isApiKeyPermissionPolicyValid(
  value: ApiKeyPermissionPolicy | null,
  options: ApiKeyPermissionOptions,
): boolean {
  if (value === null) return true;
  const { roles, restrictions } = normalizeApiKeyPermissionPolicy(value);
  const scopeValid = (scope: ApiKeyPermissionScope) =>
    scope.domain_type === "global"
      ? scope.domain_id === null
      : Boolean(scope.domain_id?.trim());
  return (
    Boolean(roles.length || restrictions.length) &&
    roles.every(
      (role) =>
        options.roles.some((option) => option.id === role.role_id) &&
        scopeValid(role),
    ) &&
    restrictions.every((restriction) => {
      const actions = options.resource_actions[restriction.resource_type] ?? [];
      const scopes = options.scope_types[restriction.resource_type] ?? [];
      return (
        restriction.actions.length > 0 &&
        restriction.actions.every((action) => actions.includes(action)) &&
        scopes.includes(restriction.domain_type) &&
        scopeValid(restriction) &&
        (restriction.resource_ids == null ||
          restriction.resource_ids.length > 0)
      );
    })
  );
}

function ScopeFields({
  value,
  onChange,
  scopes,
  context,
}: {
  value: ApiKeyPermissionScope;
  onChange: (value: ApiKeyPermissionScope) => void;
  scopes: ApiKeyScopeType[];
  context: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  const projects = useGetApiKeyPermissionTargets(
    { resourceType: "project" },
    { enabled: value.domain_type === "project" },
  );
  const missingProject =
    value.domain_id &&
    value.domain_type === "project" &&
    !projects.data?.some((project) => project.id === value.domain_id);
  return (
    <div className="space-y-2">
      <Label htmlFor={`${id}-scope`}>
        {t("apiKey.permissions.scopeFor", { context })}
      </Label>
      <select
        id={`${id}-scope`}
        className={selectClass}
        value={value.domain_type}
        onChange={(event) =>
          onChange({
            domain_type: event.target.value as ApiKeyScopeType,
            domain_id: null,
          })
        }
      >
        {scopes.map((scope) => (
          <option key={scope} value={scope}>
            {t(`apiKey.permissions.scope.${scope}`)}
          </option>
        ))}
      </select>
      {value.domain_type === "project" && (
        <>
          <Label htmlFor={`${id}-project`}>
            {t("apiKey.permissions.projectFor", { context })}
          </Label>
          <select
            id={`${id}-project`}
            className={selectClass}
            value={value.domain_id ?? ""}
            onChange={(event) =>
              onChange({ ...value, domain_id: event.target.value || null })
            }
          >
            <option value="">{t("apiKey.permissions.selectProject")}</option>
            {missingProject && (
              <option value={value.domain_id!}>
                {t("apiKey.permissions.unavailableProject", {
                  id: value.domain_id,
                })}
              </option>
            )}
            {projects.data?.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          {projects.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("apiKey.permissions.targetsError")}
            </p>
          )}
        </>
      )}
      {value.domain_type === "workspace" && (
        <>
          <Label htmlFor={`${id}-workspace`}>
            {t("apiKey.permissions.workspaceFor", { context })}
          </Label>
          <Input
            id={`${id}-workspace`}
            value={value.domain_id ?? ""}
            onChange={(event) =>
              onChange({ ...value, domain_id: event.target.value || null })
            }
            placeholder={t("apiKey.permissions.workspacePlaceholder")}
          />
        </>
      )}
    </div>
  );
}

function ResourceFields({
  restriction,
  onChange,
  context,
}: {
  restriction: ApiKeyResourceRestriction;
  onChange: (value: ApiKeyResourceRestriction) => void;
  context: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  const exact = restriction.resource_ids != null;
  const query = useGetApiKeyPermissionTargets(
    { resourceType: restriction.resource_type },
    { enabled: exact },
  );
  const targets = query.data ?? [];
  const unavailable =
    restriction.resource_ids?.filter(
      (item) => !targets.some((target) => target.id === item),
    ) ?? [];
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={exact}
          onChange={(event) =>
            onChange({
              ...restriction,
              resource_ids: event.target.checked ? [] : null,
            })
          }
        />
        {t("apiKey.permissions.specificResources", { context })}
      </label>
      {exact && (
        <>
          <Label htmlFor={`${id}-targets`}>
            {t("apiKey.permissions.resourcesFor", { context })}
          </Label>
          <select
            multiple
            id={`${id}-targets`}
            className={selectClass}
            value={restriction.resource_ids ?? []}
            onChange={(event) =>
              onChange({
                ...restriction,
                resource_ids: Array.from(
                  event.target.selectedOptions,
                  (option) => option.value,
                ),
              })
            }
          >
            {unavailable.map((item) => (
              <option key={item} value={item}>
                {t("apiKey.permissions.unavailableResource", { id: item })}
              </option>
            ))}
            {targets.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          {query.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("apiKey.permissions.targetsError")}
            </p>
          )}
          {!query.isLoading && !query.isError && !targets.length && (
            <p className="text-sm text-muted-foreground">
              {t("apiKey.permissions.noResources")}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {t("apiKey.permissions.multiselectHelp")}
          </p>
        </>
      )}
    </div>
  );
}

export default function ApiKeyPermissionsEditor({
  value,
  options,
  onChange,
}: {
  value: ApiKeyPermissionPolicy | null;
  options: ApiKeyPermissionOptions;
  onChange: (value: ApiKeyPermissionPolicy | null) => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const policy = normalizeApiKeyPermissionPolicy(
    value ?? emptyApiKeyPermissionPolicy(),
  );
  const hasRoles = policy.roles.length > 0;
  const hasRestrictions = policy.restrictions.length > 0;
  const combined = hasRoles && hasRestrictions;
  const addRole = () =>
    onChange({
      ...policy,
      roles: [
        ...policy.roles,
        { role_id: "", domain_type: "global", domain_id: null },
      ],
    });
  const addRestriction = () => {
    const resourceTypes = Object.keys(options.resource_actions);
    onChange({
      ...policy,
      restrictions: [
        ...policy.restrictions,
        {
          resource_type: resourceTypes.includes("flow")
            ? "flow"
            : (resourceTypes[0] ?? "flow"),
          actions: [],
          domain_type: "global",
          domain_id: null,
          resource_ids: null,
        },
      ],
    });
  };
  const updateRole = (
    index: number,
    patch: Partial<ApiKeyPermissionPolicy["roles"][number]>,
  ) =>
    onChange({
      ...policy,
      roles: policy.roles.map((role, item) =>
        item === index ? { ...role, ...patch } : role,
      ),
    });
  const updateRestriction = (
    index: number,
    patch: Partial<ApiKeyResourceRestriction>,
  ) =>
    onChange({
      ...policy,
      restrictions: policy.restrictions.map((restriction, item) =>
        item === index ? { ...restriction, ...patch } : restriction,
      ),
    });

  return (
    <fieldset className="space-y-4">
      <legend className="mb-2 text-sm font-medium">
        {t("apiKey.permissions.title")}
      </legend>
      <label className="flex items-center gap-2">
        <input
          name={`${id}-mode`}
          type="radio"
          checked={value !== null}
          onChange={() => onChange(emptyApiKeyPermissionPolicy())}
        />
        {t("apiKey.permissions.restricted")}
      </label>
      <label className="flex items-center gap-2">
        <input
          name={`${id}-mode`}
          type="radio"
          checked={value === null}
          onChange={() => onChange(null)}
        />
        {t("apiKey.permissions.fullAccess")}
      </label>
      <p className="text-sm text-muted-foreground">
        {t("apiKey.permissions.ownerCeiling")}
      </p>
      {value !== null && (
        <>
          {!hasRoles && !hasRestrictions && (
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={addRole}>
                {t("apiKey.permissions.useRole")}
              </Button>
              <Button type="button" variant="outline" onClick={addRestriction}>
                {t("apiKey.permissions.chooseAccess")}
              </Button>
            </div>
          )}
          {combined && (
            <p className="text-sm text-muted-foreground">
              {t("apiKey.permissions.combination")}
            </p>
          )}
          {policy.roles.map((role, index) => {
            const context = t("apiKey.permissions.roleContext", {
              count: index + 1,
            });
            const roleAvailable = options.roles.some(
              (option) => option.id === role.role_id,
            );
            return (
              <fieldset key={index} className="space-y-3 rounded-md border p-3">
                <Label htmlFor={`${id}-role-${index}`}>
                  {t("apiKey.permissions.roleLabel", { count: index + 1 })}
                </Label>
                <select
                  id={`${id}-role-${index}`}
                  className={selectClass}
                  value={role.role_id}
                  onChange={(event) =>
                    updateRole(index, { role_id: event.target.value })
                  }
                >
                  <option value="">{t("apiKey.permissions.selectRole")}</option>
                  {role.role_id && !roleAvailable && (
                    <option value={role.role_id}>
                      {t("apiKey.permissions.unavailableRole", {
                        id: role.role_id,
                      })}
                    </option>
                  )}
                  {options.roles.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
                </select>
                <ScopeFields
                  context={context}
                  value={role}
                  onChange={(scope) => updateRole(index, scope)}
                  scopes={ALL_SCOPES}
                />
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    onChange({
                      ...policy,
                      roles: policy.roles.filter((_, item) => item !== index),
                    })
                  }
                >
                  {t("apiKey.permissions.removeRole", { count: index + 1 })}
                </Button>
              </fieldset>
            );
          })}
          {hasRoles && (
            <Button type="button" variant="outline" onClick={addRole}>
              {t("apiKey.permissions.addRole")}
            </Button>
          )}
          {policy.restrictions.map((restriction, index) => {
            const context = t("apiKey.permissions.restrictionContext", {
              count: index + 1,
            });
            const actions =
              options.resource_actions[restriction.resource_type] ?? [];
            const resourceTypes = Object.keys(options.resource_actions);
            return (
              <fieldset key={index} className="space-y-3 rounded-md border p-3">
                <Label htmlFor={`${id}-resource-${index}`}>
                  {t("apiKey.permissions.resourceTypeFor", { context })}
                </Label>
                <select
                  id={`${id}-resource-${index}`}
                  className={selectClass}
                  value={restriction.resource_type}
                  onChange={(event) =>
                    updateRestriction(index, {
                      resource_type: event.target.value,
                      actions: [],
                      domain_type: "global",
                      domain_id: null,
                      resource_ids: null,
                    })
                  }
                >
                  {!resourceTypes.includes(restriction.resource_type) && (
                    <option value={restriction.resource_type}>
                      {t("apiKey.permissions.unavailableResourceType", {
                        resource: restriction.resource_type,
                      })}
                    </option>
                  )}
                  {resourceTypes.map((resource) => (
                    <option key={resource} value={resource}>
                      {t(`apiKey.permissions.resource.${resource}`)}
                    </option>
                  ))}
                </select>
                <fieldset className="space-y-2">
                  <legend className="text-sm font-medium">
                    {t("apiKey.permissions.actionsFor", { context })}
                  </legend>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                    {Array.from(
                      new Set([...actions, ...restriction.actions]),
                    ).map((action) => (
                      <label
                        key={action}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={restriction.actions.includes(action)}
                          onChange={(event) =>
                            updateRestriction(index, {
                              actions: event.target.checked
                                ? [...restriction.actions, action]
                                : restriction.actions.filter(
                                    (selected) => selected !== action,
                                  ),
                            })
                          }
                        />
                        {t(`apiKey.permissions.action.${action}`)}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <ScopeFields
                  context={context}
                  value={restriction}
                  onChange={(scope) => updateRestriction(index, scope)}
                  scopes={
                    options.scope_types[restriction.resource_type] ?? [
                      restriction.domain_type,
                    ]
                  }
                />
                <ResourceFields
                  restriction={restriction}
                  context={context}
                  onChange={(entry) => updateRestriction(index, entry)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    onChange({
                      ...policy,
                      restrictions: policy.restrictions.filter(
                        (_, item) => item !== index,
                      ),
                    })
                  }
                >
                  {t("apiKey.permissions.removeRestriction", {
                    count: index + 1,
                  })}
                </Button>
              </fieldset>
            );
          })}
          {hasRestrictions && (
            <Button type="button" variant="outline" onClick={addRestriction}>
              {t("apiKey.permissions.addRestriction")}
            </Button>
          )}
          {!combined && (hasRoles || hasRestrictions) && (
            <div className="space-y-3 border-t pt-3">
              <Button
                type="button"
                variant="ghost"
                className="h-auto px-0 py-1"
                aria-expanded={showAdvanced}
                aria-controls={`${id}-advanced`}
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {t(
                  hasRoles
                    ? "apiKey.permissions.furtherLimit"
                    : "apiKey.permissions.combineRole",
                )}
              </Button>
              <div
                id={`${id}-advanced`}
                className="space-y-3"
                hidden={!showAdvanced}
              >
                <p className="text-sm text-muted-foreground">
                  {t("apiKey.permissions.combination")}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={hasRoles ? addRestriction : addRole}
                >
                  {t(
                    hasRoles
                      ? "apiKey.permissions.chooseAccess"
                      : "apiKey.permissions.useRole",
                  )}
                </Button>
              </div>
            </div>
          )}
          {(hasRoles || hasRestrictions) &&
            !isApiKeyPermissionPolicyValid(value, options) && (
              <p className="text-sm text-muted-foreground">
                {t("apiKey.permissions.selectionRequired")}
              </p>
            )}
        </>
      )}
    </fieldset>
  );
}
