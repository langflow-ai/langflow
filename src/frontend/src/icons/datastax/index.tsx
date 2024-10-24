import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgDatastax from "./datastax";

export const DataStaxIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <SvgDatastax ref={ref} {...props} color={isDark ? "#fff" : "#000"} />;
});
