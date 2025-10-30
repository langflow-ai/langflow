import React, { forwardRef } from "react";
import MurfSVG from "./MurfSVG";

export const MurfIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <MurfSVG ref={ref} {...props} />;
  },
);
