/**
 * Asserts that a required string param is present and non-empty.
 * Throws a descriptive Error at the call site so query/mutation fns
 * fail fast rather than sending malformed requests.
 */
export function ensureRequiredParam(
  value: string | undefined | null,
  name: string,
): asserts value is string {
  if (!value) {
    throw new Error(`${name} is required`);
  }
}
