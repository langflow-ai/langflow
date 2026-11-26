import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import WebRouterIconSVG from "./WebRouterIcon";

export const WebRouterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<object>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <WebRouterIconSVG ref={ref} isDark={isDark} {...props} />;
});

export default WebRouterIcon;
