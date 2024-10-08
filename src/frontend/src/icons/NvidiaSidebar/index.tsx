import React, { forwardRef } from "react";
import NvidiaSVGSidebar from "./NvidiaSidebar";

export const NvidiaIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <NvidiaSVGSidebar ref={ref} {...props} />;
});
