import type React from "react";
import { forwardRef } from "react";
import SvgGoogleDrive from "./GoogleDrive";

export const GoogleDriveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGoogleDrive ref={ref} {...props} />;
});
