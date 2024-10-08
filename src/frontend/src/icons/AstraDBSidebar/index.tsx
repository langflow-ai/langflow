import React, { forwardRef } from "react";
import AstraSVGSidebar from "./AstraDBSidebar";

export const AstraDBIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AstraSVGSidebar ref={ref} {...props} />;
});
