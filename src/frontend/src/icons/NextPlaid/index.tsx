import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import NextPlaidIconSVG from "./NextPlaidIcon";

export const NextPlaidIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<object>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <NextPlaidIconSVG ref={ref} isDark={isDark} {...props} />;
});

export default NextPlaidIcon;
