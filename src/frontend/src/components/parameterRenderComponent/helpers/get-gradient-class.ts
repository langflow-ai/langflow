import {
  GRADIENT_DARK_CLASS,
  GRADIENT_DISABLE_DARK_CLASS,
  GRADIENT_DISABLE_WHITE_CLASS,
  GRADIENT_WHITE_CLASS,
} from "@/constants/constants";

export const getBackgroundStyle = (disabled, isDark) => {
  const backgroundClass = disabled
    ? isDark
      ? GRADIENT_DISABLE_DARK_CLASS
      : GRADIENT_DISABLE_WHITE_CLASS
    : isDark
      ? GRADIENT_DARK_CLASS
      : GRADIENT_WHITE_CLASS;

  return {
    background: backgroundClass,
    pointerEvents: "none",
  };
};
