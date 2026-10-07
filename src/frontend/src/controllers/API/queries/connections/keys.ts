/**
 * Query keys for connections and the integration catalog.
 *
 * Exported so a distribution that adds its own connection surfaces invalidates
 * the same cache entries this one reads, instead of guessing at key shapes.
 */
export const connectionsKeys = {
  all: ["connections"] as const,
  list: (provider?: string) =>
    [...connectionsKeys.all, "list", provider ?? "*"] as const,
  one: (id: string) => [...connectionsKeys.all, "one", id] as const,
  integrations: (provider?: string, includeBlocked?: boolean) =>
    [
      ...connectionsKeys.all,
      "integrations",
      provider ?? "*",
      includeBlocked ? "with-blocked" : "visible",
    ] as const,
  effectivePolicy: () =>
    [...connectionsKeys.all, "policy", "effective"] as const,
  registrations: (provider?: string) =>
    [
      ...connectionsKeys.all,
      "oauth",
      "registrations",
      provider ?? "*",
    ] as const,
} as const;
