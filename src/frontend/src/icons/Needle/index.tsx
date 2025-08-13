import type React from "react";
import { forwardRef } from "react";
import NeedleSvg from "./needle-icon.svg?react";

export const NeedleIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <NeedleSvg ref={ref} {...props} />;
});
