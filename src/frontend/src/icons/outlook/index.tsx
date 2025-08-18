import type React from "react";
import { forwardRef } from "react";
import OutlookIconSVG from "./outlook";

export const OutlookIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <OutlookIconSVG ref={ref} {...props} />;
});
