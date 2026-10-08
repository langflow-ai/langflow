import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import SvgFlexAI from "./FlexAIIcon";

export const FlexAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <SvgFlexAI ref={ref} isDark={isDark} {...props} />;
});
