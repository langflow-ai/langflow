export type DarkStoreType = {
  dark: boolean;
  stars: number;
  gradientIndex: number;
  version: string;
  setVersion: (version: string) => void;
  setDark: (dark: boolean) => void;
  setStars: (stars: number) => void;
  setGradientIndex: (gradientIndex: number) => void;
};
