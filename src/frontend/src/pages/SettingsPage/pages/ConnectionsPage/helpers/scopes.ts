import type { IntegrationCapabilityRead } from "@/controllers/API/queries/connections";
import type { APIClassType, APIDataType } from "@/types/api";
import { CONNECTION_REF_FIELD_TYPE } from "@/utils/connection-ref-gate";
import {
  normalizeScope,
  uniqueNormalizedScopes,
} from "@/utils/connection-scopes";

export interface ConditionalScope {
  scope: string;
  input?: string;
  condition?: "input_present" | "input_truthy";
}

export interface ScopeRequirement {
  capabilityId: string;
  displayName: string;
  requiredScopes: string[];
  conditionalScopes: ConditionalScope[];
}

type ConnectionRefTemplate = {
  type?: string;
  required_scopes?: string[];
  conditional_scopes?: (ConditionalScope | string)[];
};

/** Providers publish scopes as URLs (Google, Microsoft) or bare names (Slack). */
export const shortScope = (scope: string): string => {
  const trimmed = scope.trim().replace(/\/+$/, "");
  if (!trimmed.includes("://")) return trimmed;
  return trimmed.split("/").pop() || trimmed;
};

/**
 * The capability manifest names the component each action runs through, and the
 * component's `connection_ref` field carries the scopes. Reading them from the
 * template keeps one source of truth: the backend compares the same strings.
 */
export const findComponentByRef = (
  data: APIDataType | undefined,
  componentRef: string | null | undefined,
): APIClassType | undefined => {
  if (!data || !componentRef) return undefined;
  for (const category of Object.values(data)) {
    if (!category || typeof category !== "object") continue;
    for (const [key, component] of Object.entries(category)) {
      // Canonical keys look like `ext:google:GmailSendComponent@official`.
      if (
        key === componentRef ||
        key.includes(`:${componentRef}@`) ||
        key.endsWith(`:${componentRef}`)
      ) {
        return component as APIClassType;
      }
    }
  }
  return undefined;
};

const connectionRefField = (
  component: APIClassType | undefined,
): ConnectionRefTemplate | undefined => {
  const template = component?.template as
    | Record<string, ConnectionRefTemplate>
    | undefined;
  if (!template) return undefined;
  return Object.values(template).find(
    (field) => field && field.type === CONNECTION_REF_FIELD_TYPE,
  );
};

const normalizeConditional = (
  entry: ConditionalScope | string,
): ConditionalScope => (typeof entry === "string" ? { scope: entry } : entry);

export function scopeRequirements(
  capabilities: IntegrationCapabilityRead[],
  data: APIDataType | undefined,
): ScopeRequirement[] {
  return capabilities.map((capability) => {
    const field = connectionRefField(
      findComponentByRef(data, capability.component_ref),
    );
    return {
      capabilityId: capability.id,
      displayName: capability.display_name,
      requiredScopes: [...(field?.required_scopes ?? [])],
      conditionalScopes: (field?.conditional_scopes ?? []).map(
        normalizeConditional,
      ),
    };
  });
}

export const uniqueScopes = (requirements: ScopeRequirement[]): string[] => {
  const seen = new Set<string>();
  for (const requirement of requirements) {
    for (const scope of requirement.requiredScopes) seen.add(scope);
    for (const conditional of requirement.conditionalScopes) {
      seen.add(conditional.scope);
    }
  }
  return [...seen];
};

/**
 * The registration's scope list is the operator's ceiling for a start request.
 * `oauth/start` checks it verbatim (`set(scopes) <= set(registration.scopes)`
 * in `connection/oauth/broker.py`), so this compares exact strings too.
 */
export function partitionByCeiling(
  scopes: string[],
  ceiling: string[] | undefined,
): { requestable: string[]; unavailable: string[] } {
  if (!ceiling) return { requestable: scopes, unavailable: [] };
  const allowed = new Set(ceiling);
  return {
    requestable: scopes.filter((scope) => allowed.has(scope)),
    unavailable: scopes.filter((scope) => !allowed.has(scope)),
  };
}

export interface ReauthorizeScopeList {
  /** Every scope the dialog offers, spelled as the registration lists it. */
  options: string[];
  /** The options the connection already holds; they start checked. */
  granted: string[];
  /** Granted scopes this registration cannot request again. */
  outsideCeiling: string[];
}

/**
 * The scope list for re-authorizing a connection: what the provider's actions
 * can request, plus every scope the connection already holds, so a new consent
 * never drops a grant the user did not clear.
 *
 * A granted scope matches a requestable one the way the backend compares
 * coverage (`normalizeScope`), so a granted `Mail.Send` checks the requestable
 * `https://graph.microsoft.com/Mail.Send`. The request itself must name each
 * scope as the registration lists it, because `oauth/start` compares the
 * ceiling verbatim; a granted scope the ceiling does not list in any spelling
 * cannot be requested and is reported instead.
 */
export function reauthorizeScopeList({
  provider,
  requestable,
  granted,
  ceiling,
}: {
  provider: string;
  requestable: string[];
  granted: string[];
  /** The registration's scopes; undefined when the backend does not list them. */
  ceiling: string[] | undefined;
}): ReauthorizeScopeList {
  const key = (scope: string) => normalizeScope(provider, scope);
  const listed = new Set(requestable.map(key));
  const extra = uniqueNormalizedScopes(provider, granted)
    .filter((scope) => !listed.has(key(scope)))
    .map((scope) => ({
      scope,
      // Without a ceiling to check against, ask for the scope as granted.
      requestAs: ceiling
        ? ceiling.find((allowed) => key(allowed) === key(scope))
        : scope,
    }));
  const options = [
    ...requestable,
    ...extra.flatMap(({ requestAs }) => (requestAs ? [requestAs] : [])),
  ];
  const grantedKeys = new Set(granted.map(key));
  return {
    options,
    granted: options.filter((scope) => grantedKeys.has(key(scope))),
    outsideCeiling: extra
      .filter(({ requestAs }) => !requestAs)
      .map(({ scope }) => scope),
  };
}
