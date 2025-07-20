import React, { forwardRef } from "react";
import SvgMcpIcon from "./McpIcon";

export const McpIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgMcpIcon ref={ref} {...props} />;
  },
);
