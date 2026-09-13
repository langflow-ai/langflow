// tests/globalTeardown.ts

import fs from "fs";
import path from "path";
import {
  getE2EDatabaseDirectory,
  isAuthzE2EMode,
} from "./utils/authz-e2e-mode.mjs";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// On Windows, the uvicorn process can still hold SQLite file handles when
// teardown runs. POSIX allows unlinking files with open handles; Win32 does
// not, surfacing as EBUSY/EPERM. Retry with backoff, fall back to walking the
// tree and removing children individually, and never throw out of teardown.
async function removeWithRetry(target: string): Promise<boolean> {
  const attempts = 5;
  for (let i = 0; i < attempts; i++) {
    try {
      fs.rmSync(target, { recursive: true, force: true });
      if (!fs.existsSync(target)) return true;
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code !== "EBUSY" && code !== "EPERM" && code !== "ENOTEMPTY") {
        throw err;
      }
    }
    await sleep(200 * 2 ** i);
  }
  return !fs.existsSync(target);
}

function removeChildrenBestEffort(target: string): string[] {
  const failed: string[] = [];
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(target, { withFileTypes: true });
  } catch {
    return failed;
  }
  for (const entry of entries) {
    const childPath = path.join(target, entry.name);
    try {
      fs.rmSync(childPath, { recursive: true, force: true });
    } catch {
      failed.push(childPath);
    }
  }
  return failed;
}

export default async () => {
  const targets = [
    path.join(__dirname, "..", getE2EDatabaseDirectory()),
    path.join(
      __dirname,
      "..",
      isAuthzE2EMode() ? "temp-authz-config" : "temp-config",
    ),
  ];

  for (const target of targets) {
    console.warn("Removing E2E temporary path", target);
    if (!fs.existsSync(target)) continue;

    try {
      if (await removeWithRetry(target)) continue;

      const stragglers = removeChildrenBestEffort(target);
      if (await removeWithRetry(target)) continue;

      console.warn(
        `Temporary path still present after retries; leaving it for runner cleanup. Files that resisted removal: ${stragglers.length}`,
      );
    } catch (error) {
      console.error("Error while removing E2E temporary path:", error);
    }
  }
};
