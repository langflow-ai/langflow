import fetch from "node-fetch";
import { getURL } from "../controllers/API/helpers/constants";

export async function getBackendRootPath(target: string) {
  let rootPath = "";
  const configURL = getURL("CONFIG");
  try {
    console.log("Fetching config from:", `${target}${configURL}`);
    const response = await fetch(`${target}${configURL}`);
    if (!response.ok) {
      console.warn(
        `Failed to fetch config: ${response.status}, using empty root path`,
      );
      return "";
    }

    const data = await response.json();
    if (!data || typeof data.root_path !== "string") {
      console.warn(
        "Invalid config response: root_path is missing or invalid, using empty root path",
      );
      return "";
    }

    rootPath = data.root_path;
    console.log("Using root path:", rootPath);

    // Set the environment variable
    process.env.ROOT_PATH = rootPath;

    // Verify it was set correctly
    if (process.env.ROOT_PATH !== rootPath) {
      console.warn(
        "Failed to set ROOT_PATH environment variable, using empty root path",
      );
      return "";
    }
  } catch (error) {
    console.warn("Failed to fetch or set backend config:", error);
    console.warn("Using empty root path");
    return "";
  }
  return rootPath;
}
