export type DarkStoreType = {
  dark: boolean;
  stars: number;
  version: string;
  latestVersion: string;
  setDark: (dark: boolean) => void;
  refreshVersion: (v: string) => void;
  refreshLatestVersion: (v: string) => void;
  refreshStars: () => void;
  discordCount: number;
  refreshDiscordCount: () => void;
};
