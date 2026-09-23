import type React from "react";
import { forwardRef } from "react";
import SvgRequesty from "./RequestyIcon";

export const RequestyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgRequesty ref={ref} {...props} />;
});
