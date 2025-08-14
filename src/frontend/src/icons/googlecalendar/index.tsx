import type React from "react";
import { forwardRef } from "react";
import GooglecalendarIconSVG from "./googlecalendar";

export const GooglecalendarIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GooglecalendarIconSVG ref={ref} {...props} />;
});
