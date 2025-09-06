import React, { forwardRef } from "react";
import AsanaIconSVG from "./asana";

export const AsanaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <AsanaIconSVG ref={ref} {...props} />;
  },
);
