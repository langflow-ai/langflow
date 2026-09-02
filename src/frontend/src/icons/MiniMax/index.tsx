import type React from "react";
import { forwardRef } from "react";
import MiniMaxSVG from "./MiniMaxIcon";

export const MiniMaxIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MiniMaxSVG ref={ref} {...props} />;
});
