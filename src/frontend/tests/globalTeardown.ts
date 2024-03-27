// tests/globalTeardown.ts
import { unlinkSync } from "fs";
import { resolve } from "path";

export default async () => {
  try {
    unlinkSync(resolve(__dirname, "../temp"));
    console.log("Successfully removed the temp database");
  } catch (error) {
    console.error("Error while removing the temp database:", error);
  }
};
