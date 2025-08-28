import type React from "react";
import { forwardRef } from "react";
import UpstashIcon from "./UpstashIcon";

export const UpstashSvgIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <UpstashIcon ref={ref} {...props} />;
});
