import type React from "react";
import { forwardRef } from "react";
import SvgOceanBase from "./OceanBase";

export const OceanBaseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOceanBase ref={ref} {...props} />;
});
