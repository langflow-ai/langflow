import React, { forwardRef } from "react";
import GoogleTasksIconSVG from "./googletasks";

export const GoogleTasksIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GoogleTasksIconSVG ref={ref} {...props} />;
});