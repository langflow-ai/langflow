import React, { forwardRef } from "react";
import SvgOneDrive from "./OneDrive";

export const OneDriveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOneDrive ref={ref} {...props} />;
});
