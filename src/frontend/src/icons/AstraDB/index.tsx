import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import AstraSVG from "./AstraDB";

export const AstraDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <AstraSVG ref={ref} isDark={isDark} {...props} />;
});
