import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  AUTHZ_JOURNEY_IDS,
  AUTHZ_STARTUP_LOG,
  assertAuthzStartup,
  getE2EArtifactNamespace,
  getE2EDatabaseDirectory,
  getE2ETestIgnore,
  inspectAuthzJourneyTitles,
  isAuthzE2EMode,
} from "./authz-e2e-mode.mjs";

test("keeps normal and authorization E2E state isolated", () => {
  assert.equal(isAuthzE2EMode({}), false);
  assert.equal(getE2EArtifactNamespace({}), "core");
  assert.equal(getE2EDatabaseDirectory({}), "temp");
  assert.ok(getE2ETestIgnore({}).includes("**/core/features/authz/**"));

  const authzEnv = { LANGFLOW_E2E_AUTHZ: "true" };
  assert.equal(isAuthzE2EMode(authzEnv), true);
  assert.equal(getE2EArtifactNamespace(authzEnv), "authz");
  assert.equal(getE2EDatabaseDirectory(authzEnv), "temp-authz");
  assert.ok(!getE2ETestIgnore(authzEnv).includes("**/core/features/authz/**"));
});

test("accepts exactly one occurrence of every authorization journey", () => {
  const titles = AUTHZ_JOURNEY_IDS.map((id) => `[${id}] scenario`);
  assert.deepEqual(inspectAuthzJourneyTitles(titles), {
    valid: true,
    missing: [],
    duplicates: [],
  });
});

test("rejects missing, duplicate, and extra authorization journeys", () => {
  const titles = AUTHZ_JOURNEY_IDS.slice(1).map((id) => `[${id}] scenario`);
  titles.push(`[${AUTHZ_JOURNEY_IDS[1]}] duplicate`, "untracked scenario");
  const result = inspectAuthzJourneyTitles(titles);
  assert.equal(result.valid, false);
  assert.deepEqual(result.missing, [AUTHZ_JOURNEY_IDS[0]]);
  assert.deepEqual(result.duplicates, [AUTHZ_JOURNEY_IDS[1]]);
});

test("requires the running Casbin service with enabled, ready collaboration", () => {
  const startup =
    "Authorization service=CasbinAuthorizationService enabled=True ready=True team_roles=True sharing=True invalid_teams=0";
  assert.equal(assertAuthzStartup(startup), startup);
  for (const rejected of [
    "",
    startup.replace(
      "CasbinAuthorizationService",
      "LangflowAuthorizationService",
    ),
    startup.replace("enabled=True", "enabled=False"),
    startup.replace("ready=True", "ready=False"),
    startup.replace("team_roles=True", "team_roles=False"),
    startup.replace("sharing=True", "sharing=False"),
    startup.replace("invalid_teams=0", "invalid_teams=1"),
    `${startup}\n${startup}`,
  ]) {
    assert.throws(
      () => assertAuthzStartup(rejected),
      /registered Casbin authorization/,
    );
  }
});

test("prepares explicit service registration and clears stale startup evidence", (t) => {
  const root = mkdtempSync(path.join(tmpdir(), "langflow-authz-config-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const prepare = () =>
    execFileSync(
      process.execPath,
      [
        fileURLToPath(
          new URL("../fixtures/prepare-authz-server.mjs", import.meta.url),
        ),
      ],
      { cwd: root, env: { ...process.env, LANGFLOW_E2E_AUTHZ: "true" } },
    );
  prepare();
  const configDir = path.join(root, "temp-authz-config");
  assert.equal(
    readFileSync(path.join(configDir, "lfx.toml"), "utf8"),
    '[services]\nauthorization_service = "langflow.services.authorization.casbin.service:CasbinAuthorizationService"\n',
  );
  const logPath = path.join(root, AUTHZ_STARTUP_LOG);
  writeFileSync(logPath, "stale successful startup");
  prepare();
  assert.equal(readFileSync(logPath, "utf8"), "");
});
