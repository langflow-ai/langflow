import React, { forwardRef } from "react";
import CursorSVG from "./Cursor";

export const CursorIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <CursorSVG ref={ref} {...props} />;
});
