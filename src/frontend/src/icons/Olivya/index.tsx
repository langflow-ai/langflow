import type React from "react";
import { forwardRef } from "react";
import OlivyaSVG from "./olivya";

export const OlivyaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <OlivyaSVG ref={ref} {...props} />;
});
