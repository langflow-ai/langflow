import { useDarkStore } from "@/stores/darkStore";

export const customRefreshLatestVersion = (version: string) => {
  const refreshLatestVersion = useDarkStore.getState().refreshLatestVersion;
  refreshLatestVersion(version);
};
