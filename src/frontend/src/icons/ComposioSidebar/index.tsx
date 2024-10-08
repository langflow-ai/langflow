import React, { forwardRef } from "react";
import ComposioIconSVGSidebar from "./ComposioSidebar";

export const ComposioIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ComposioIconSVGSidebar ref={ref} {...props} />;
});
