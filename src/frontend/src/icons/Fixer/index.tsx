import React, { forwardRef } from "react";
import FixerIconSVG from "./fixer";

export const FixerIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <FixerIconSVG ref={ref} {...props} />;
  },
);
