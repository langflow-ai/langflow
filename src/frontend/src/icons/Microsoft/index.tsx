import type React from "react";
import { forwardRef } from "react";
import SvgMicrosoft from "./Microsoft";

export const MicrosoftIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMicrosoft ref={ref} {...props} />;
});
