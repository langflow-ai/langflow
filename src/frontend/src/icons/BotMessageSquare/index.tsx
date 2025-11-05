import type React from "react";
import { forwardRef } from "react";
import SvgChroma from "./BotMessageSquare";

export const BotMessageSquareIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgChroma ref={ref} {...props} />;
});
