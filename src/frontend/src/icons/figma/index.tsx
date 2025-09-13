import React, { forwardRef } from "react";
import FigmaIconSVG from "./figma";

export const FigmaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <FigmaIconSVG ref={ref} {...props} />;
  },
);
