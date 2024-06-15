import React, { forwardRef } from "react";
import SvgShare from "./Share";

export const ShareIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgShare ref={ref} {...props} />;
  },
);
