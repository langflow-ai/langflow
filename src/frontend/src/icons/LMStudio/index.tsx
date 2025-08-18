import type React from "react";
import { forwardRef } from "react";
import SvgLMStudio from "./LMStudioIcon";

export const LMStudioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgLMStudio ref={ref} {...props} />;
});
