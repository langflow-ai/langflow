/**
 * Scope matching for managed connections, mirrored from the backend so the
 * picker and the Connections page agree with the run-time check. Everything
 * here follows `src/lfx/src/lfx/integrations/capabilities.py` (`ScopeSet`,
 * `ScopeCondition`); change the two together.
 */

const GOOGLE_SCOPE_PREFIX = "https://www.googleapis.com/auth/";
const MICROSOFT_SCOPE_PREFIX = "https://graph.microsoft.com/";

/** When a conditional scope applies, as `ScopeCondition` declares it. */
export interface ScopeCondition {
  kind: "input_present" | "input_truthy";
  /** Name of the component input the condition reads. */
  input: string;
}

/** A scope an action needs only for some inputs (`ConditionalScopeRequirement`). */
export interface ConditionalScopeRequirement {
  scope: string;
  role?: "optional" | "alternative";
  condition: ScopeCondition;
}

const removePrefix = (value: string, prefix: string): string =>
  value.startsWith(prefix) ? value.slice(prefix.length) : value;

/**
 * Mirrors `ScopeSet._normalize`: Google and Microsoft accept a scope with or
 * without their URL prefix, and providers compare scopes case-insensitively.
 * `toLowerCase()` stands in for Python's `casefold()`.
 */
export function normalizeScope(provider: string | undefined, scope: string) {
  let normalized = scope.trim();
  if (provider === "google" || provider === "google_workspace") {
    normalized = removePrefix(normalized, GOOGLE_SCOPE_PREFIX);
  } else if (provider === "microsoft") {
    normalized = removePrefix(normalized, MICROSOFT_SCOPE_PREFIX);
  }
  return normalized.toLowerCase();
}

/**
 * Mirrors `ScopeSet.missing`: the required scopes `granted` does not cover,
 * in their original spelling so a message names what the action declared.
 */
export function missingScopes(
  provider: string | undefined,
  required: string[],
  granted: string[],
): string[] {
  const covered = new Set(
    granted.map((scope) => normalizeScope(provider, scope)),
  );
  return required.filter(
    (scope) => !covered.has(normalizeScope(provider, scope)),
  );
}

/** Drops scopes that normalize to one already listed, keeping the first spelling. */
export function uniqueNormalizedScopes(
  provider: string | undefined,
  scopes: string[],
): string[] {
  const seen = new Set<string>();
  return scopes.filter((scope) => {
    const key = normalizeScope(provider, scope);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Python's `bool()` for the JSON values a component input can hold: `None`,
 * `False`, zero, and empty strings, lists and dicts are falsy. Unlike
 * JavaScript, NaN is truthy.
 */
export function isPythonTruthy(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string" || Array.isArray(value)) {
    return value.length > 0;
  }
  if (value instanceof Map || value instanceof Set) return value.size > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

/** Mirrors `ScopeCondition.is_active`. */
export function isScopeConditionActive(
  condition: ScopeCondition | undefined,
  inputs: Record<string, unknown>,
): boolean {
  if (!condition?.input) return false;
  if (condition.kind === "input_present") {
    return condition.input in inputs && inputs[condition.input] != null;
  }
  if (condition.kind === "input_truthy") {
    return isPythonTruthy(inputs[condition.input]);
  }
  return false;
}

/**
 * The scopes a `connection_ref` field needs for the inputs as they are now:
 * its required scopes plus every conditional scope whose condition holds, the
 * same set `Component.resolve_connection` asks the resolver to cover.
 */
export function activeRequiredScopes(
  provider: string | undefined,
  requiredScopes: string[],
  conditionalScopes: ConditionalScopeRequirement[] | undefined,
  inputs: Record<string, unknown>,
): string[] {
  const active = (conditionalScopes ?? [])
    .filter(
      (requirement) =>
        typeof requirement?.scope === "string" &&
        isScopeConditionActive(requirement.condition, inputs),
    )
    .map((requirement) => requirement.scope);
  return uniqueNormalizedScopes(provider, [...requiredScopes, ...active]);
}

/**
 * A node's input values keyed by input name, read from its template. A value
 * that arrives over an edge is only known at run time, so the field's own
 * value is the best the canvas can offer; the run-time check stays
 * authoritative.
 */
export function templateInputValues(
  template: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const [name, field] of Object.entries(template ?? {})) {
    if (field && typeof field === "object" && !Array.isArray(field)) {
      values[name] = (field as { value?: unknown }).value;
    }
  }
  return values;
}
