export type DarkStoreType = {
    dark: boolean;
    stars: number;
    gradientIndex: number;
    setDark: (dark: boolean) => void;
    setStars: (stars: number) => void;
    setGradientIndex: (gradientIndex: number) => void;
  };