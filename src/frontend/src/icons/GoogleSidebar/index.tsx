import React, { forwardRef } from "react";
import SvgGoogleSidebar from "./GoogleSidebar";

export const GoogleIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGoogleSidebar ref={ref} {...props} />;
});
