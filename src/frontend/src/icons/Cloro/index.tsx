import type React from "react";
import { forwardRef } from "react";
import SvgCloro from "./Cloro";

// The mark is one colour: black on a light canvas, white on a dark one.
export const CloroIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgCloro ref={ref} {...props} />;
});
