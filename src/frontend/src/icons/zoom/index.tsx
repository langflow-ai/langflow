import React, { forwardRef } from "react";
import ZoomIconSVG from "./zoom";

export const ZoomIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <ZoomIconSVG ref={ref} {...props} />;
  },
);
