import React, { forwardRef } from "react";
import MurfSVG from "./murf-icon.svg?react";

export const MurfIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <MurfSVG ref={ref} {...props} />;
  },
);
