import type React from "react";
import { forwardRef } from "react";
import SvgPopNow from "./PopNowIcon";

export const PopNowIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPopNow ref={ref} {...props} />;
});
