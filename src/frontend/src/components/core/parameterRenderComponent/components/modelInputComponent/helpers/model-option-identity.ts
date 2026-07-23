import type { ModelOption } from "../types";

type ModelIdentity = Pick<ModelOption, "name"> &
  Partial<Pick<ModelOption, "provider">>;

/**
 * Match structured model values by provider and name. Older flows may not
 * include a provider, so those values retain the legacy name-only behavior.
 */
export const matchesModelIdentity = (
  option: ModelIdentity,
  saved: ModelIdentity,
): boolean =>
  option.name === saved.name &&
  (!saved.provider || option.provider === saved.provider);
