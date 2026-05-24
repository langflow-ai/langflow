// tests/globalTeardown.ts

import fs from "fs";
import path from "path";

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
  console.warn("Removing the temp database");
  // this file is in src/frontend/tests/globalTeardown.ts
  // temp is in src/frontend/temp
  const tempDbPath = path.join(__dirname, "..", "temp");
  console.warn("tempDbPath", tempDbPath);

  if (!fs.existsSync(tempDbPath)) {
    console.warn("Temp database directory does not exist, skipping removal");
    return;
  }

  try {
    if (await removeWithRetry(tempDbPath)) {
      console.warn("Successfully removed the temp database");
      return;
    }

    const stragglers = removeChildrenBestEffort(tempDbPath);
    if (await removeWithRetry(tempDbPath)) {
      console.warn(
        "Successfully removed the temp database after per-file fallback",
      );
      return;
    }

    console.warn(
      `Temp database directory still present after retries; leaving it for the runner workspace cleanup. Files that resisted removal: ${stragglers.length}`,
    );
  } catch (error) {
    console.error("Error while removing the temp database:", error);
  }
};
