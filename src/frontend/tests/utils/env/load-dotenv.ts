import * as dotenv from "dotenv";
import path from "path";

/**
 * Load the local .env when not running in CI. Idempotent.
 *
 * Specs that need env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) used
 * to copy-paste a 3-line `if (!process.env.CI) { dotenv.config(...) }`
 * block. Call this helper instead — once at module load, or via the
 * Playwright globalSetup once that wiring lands.
 *
 * @param specDir Pass `__dirname` from the calling spec so the relative
 *                path to `tests/.env` resolves correctly.
 */
export function loadDotenvIfLocal(specDir: string): void {
  if (process.env.CI) return;
  dotenv.config({ path: path.resolve(specDir, "../../.env") });
}
