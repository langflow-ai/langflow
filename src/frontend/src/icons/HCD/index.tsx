import React, { forwardRef } from "react";
import HCDSVG from "./HCD";

export const HCDIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <HCDSVG ref={ref} {...props} />;
  },
);
