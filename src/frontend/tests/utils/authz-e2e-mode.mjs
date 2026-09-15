export const AUTHZ_STARTUP_LOG = "temp-authz-config/authz-startup.log";

export const AUTHZ_JOURNEY_IDS = Object.freeze(
  Array.from(
    { length: 8 },
    (_, index) => `AUTHZ-JOURNEY-${String(index + 1).padStart(2, "0")}`,
  ),
);

export function isAuthzE2EMode(env = process.env) {
  return env.LANGFLOW_E2E_AUTHZ === "true";
}

export function getE2EArtifactNamespace(env = process.env) {
  return isAuthzE2EMode(env) ? "authz" : "core";
}

export function getE2EDatabaseDirectory(env = process.env) {
  return isAuthzE2EMode(env) ? "temp-authz" : "temp";
}

export function getE2ETestIgnore(env = process.env) {
  return isAuthzE2EMode(env)
    ? ["**/live/**"]
    : ["**/live/**", "**/core/features/authz/**"];
}

export function inspectAuthzJourneyTitles(titles) {
  const counts = new Map(AUTHZ_JOURNEY_IDS.map((id) => [id, 0]));
  for (const title of titles) {
    for (const id of AUTHZ_JOURNEY_IDS) {
      if (String(title).includes(`[${id}]`)) {
        counts.set(id, (counts.get(id) ?? 0) + 1);
      }
    }
  }

  const missing = AUTHZ_JOURNEY_IDS.filter((id) => counts.get(id) === 0);
  const duplicates = AUTHZ_JOURNEY_IDS.filter(
    (id) => (counts.get(id) ?? 0) > 1,
  );
  return {
    valid:
      titles.length === AUTHZ_JOURNEY_IDS.length &&
      missing.length === 0 &&
      duplicates.length === 0,
    missing,
    duplicates,
  };
}

export function assertAuthzStartup(log) {
  const reports =
    log.match(
      /Authorization service=\S+ enabled=\S+ ready=\S+ team_roles=\S+ sharing=\S+ invalid_teams=\d+/g,
    ) ?? [];
  const expected =
    "Authorization service=CasbinAuthorizationService enabled=True ready=True team_roles=True sharing=True invalid_teams=0";
  if (reports.length !== 1 || reports[0] !== expected) {
    throw new Error(
      "Authorization E2E requires one registered Casbin authorization startup with enforcement and collaboration ready.",
    );
  }
  return reports[0];
}
