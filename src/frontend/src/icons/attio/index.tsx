import React, { forwardRef } from "react";
import AttioIconSVG from "./attio";

export const AttioIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <AttioIconSVG ref={ref} {...props} />;
  },
);
