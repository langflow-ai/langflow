import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgCleanlab from "./Cleanlab";

export const CleanlabIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <SvgCleanlab ref={ref} isdark={isdark} {...props} />;
});
