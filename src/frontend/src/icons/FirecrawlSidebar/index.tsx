import React, { forwardRef } from "react";
import SvgFirecrawlLogoSidebar from "./FirecrawlLogoSidebar";

export const FirecrawlIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgFirecrawlLogoSidebar ref={ref} {...props} />;
});
