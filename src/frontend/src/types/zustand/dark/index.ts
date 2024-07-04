export type DarkStoreType = {
  dark: boolean;
  stars: number;
  version: string;
  setDark: (dark: boolean) => void;
  refreshVersion: (v: string) => void;
  refreshStars: () => void;
};
