import React, { forwardRef } from "react";
import FreshdeskIconSVG from "./freshdesk";

export const FreshdeskIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <FreshdeskIconSVG ref={ref} {...props} />;
});
