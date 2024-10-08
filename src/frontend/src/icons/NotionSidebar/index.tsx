import React, { forwardRef } from "react";
import SvgNotionLogoSidebar from "./NotionSidebar";

export const NotionIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgNotionLogoSidebar ref={ref} {...props} />;
});
