import React, { forwardRef } from "react";
import SvgLinkup from "./Linkup";

export const LinkupIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgLinkup ref={ref} {...props} />;
});
