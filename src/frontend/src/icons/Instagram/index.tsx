import React, { forwardRef } from "react";
import InstagramIconSVG from "./instagram";

export const InstagramIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <InstagramIconSVG ref={ref} {...props} />;
});
