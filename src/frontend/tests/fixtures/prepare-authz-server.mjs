import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { AUTHZ_STARTUP_LOG, isAuthzE2EMode } from "../utils/authz-e2e-mode.mjs";

if (!isAuthzE2EMode()) {
  throw new Error(
    "Authorization server setup requires LANGFLOW_E2E_AUTHZ=true.",
  );
}

const configDir = path.resolve("temp-authz-config");
mkdirSync(configDir, { recursive: true });
writeFileSync(
  path.join(configDir, "lfx.toml"),
  '[services]\nauthorization_service = "langflow.services.authorization.casbin.service:CasbinAuthorizationService"\n',
);
writeFileSync(AUTHZ_STARTUP_LOG, "");
