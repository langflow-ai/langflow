import React, { forwardRef } from "react";
import One_DriveIconSVG from "./one_drive";

export const One_DriveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <One_DriveIconSVG ref={ref} {...props} />;
});
