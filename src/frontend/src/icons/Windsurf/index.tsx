import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgWindsurf from "./Windsurf";

export const WindsurfIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <SvgWindsurf ref={ref} isdark={isdark} {...props} />;
});
