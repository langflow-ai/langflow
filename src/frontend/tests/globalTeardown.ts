// tests/globalTeardown.ts

import fs from "fs";
import path from "path";

export default async () => {
  try {
    console.log("Removing the temp database");
    // Check if the file exists in the path
    // this file is in src/frontend/tests/globalTeardown.ts
    // temp is in src/frontend/temp
    const tempDbPath = path.join(__dirname, "..", "temp");
    console.log("tempDbPath", tempDbPath);
    // Remove the temp database
    fs.rmSync(tempDbPath);
    // Check if the file is removed
    if (!fs.existsSync(tempDbPath)) {
      console.log("Successfully removed the temp database");
    } else {
      console.error("Error while removing the temp database");
    }
  } catch (error) {
    console.error("Error while removing the temp database:", error);
  }
};
