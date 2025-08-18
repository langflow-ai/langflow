// tests/globalTeardown.ts

import fs from "fs";
import path from "path";

export default async () => {
  try {
    console.warn("Removing the temp database");
    // Check if the file exists in the path
    // this file is in src/frontend/tests/globalTeardown.ts
    // temp is in src/frontend/temp
    const tempDbPath = path.join(__dirname, "..", "temp");
    console.warn("tempDbPath", tempDbPath);

    // Check if the directory exists before attempting to remove it
    if (fs.existsSync(tempDbPath)) {
      // Remove the temp database
      fs.rmSync(tempDbPath, { recursive: true, force: true });

      // Check if the file is removed
      if (!fs.existsSync(tempDbPath)) {
        console.warn("Successfully removed the temp database");
      } else {
        console.error(
          "Error: temp database still exists after removal attempt",
        );
      }
    } else {
      console.warn("Temp database directory does not exist, skipping removal");
    }
  } catch (error) {
    console.error("Error while removing the temp database:", error);
  }
};
