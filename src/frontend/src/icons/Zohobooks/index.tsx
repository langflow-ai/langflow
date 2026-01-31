import React, { forwardRef } from "react";
import ZohobooksIconSVG from "./zohobooks";

export const ZohobooksIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ZohobooksIconSVG ref={ref} {...props} />;
});
