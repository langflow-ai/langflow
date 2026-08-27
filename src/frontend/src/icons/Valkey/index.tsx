import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import SvgValkey from "./Valkey";

export const ValkeyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <SvgValkey ref={ref} isDark={isDark} {...props} />;
});
