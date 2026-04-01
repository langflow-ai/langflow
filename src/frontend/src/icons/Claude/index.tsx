import type React from "react";
import { forwardRef } from "react";
import ClaudeSVG from "./Claude";

export const ClaudeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ClaudeSVG ref={ref} {...props} />;
});
