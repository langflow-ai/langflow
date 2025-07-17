import type React from "react";
import { forwardRef } from "react";
import SvgSpiderIcon from "./SpiderIcon";

export const SpiderIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSpiderIcon ref={ref} {...props} />;
});
