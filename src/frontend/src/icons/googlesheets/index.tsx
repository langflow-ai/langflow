import React, { forwardRef } from "react";
import GooglesheetsIconSVG from "./googlesheets";

export const GooglesheetsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GooglesheetsIconSVG ref={ref} {...props} />;
});