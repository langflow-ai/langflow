import type React from "react";
import { forwardRef } from "react";
import SvgRuncrate from "./RuncrateIcon";

export const RuncrateIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgRuncrate ref={ref} {...props} />;
});
