import React, { forwardRef } from "react";
import DSESVG from "./DSE";

export const DSEIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <DSESVG ref={ref} {...props} />;
  },
);
