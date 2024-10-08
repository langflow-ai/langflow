import React, { forwardRef } from "react";
import SvgCohereSidebar from "./CohereSidebar";

export const CohereIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCohereSidebar ref={ref} {...props} />;
});
