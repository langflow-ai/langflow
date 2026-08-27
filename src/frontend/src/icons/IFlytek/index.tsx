import type React from "react";
import { forwardRef } from "react";
import SvgIFlytek from "./IFlytekIcon";

export const IFlytekIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgIFlytek ref={ref} {...props} />;
});
