import type React from "react";
import { forwardRef } from "react";
import DeepSeekSVG from "./DeepSeekIcon";

export const DeepSeekIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DeepSeekSVG ref={ref} {...props} />;
});
