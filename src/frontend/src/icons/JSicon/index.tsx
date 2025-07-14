import React, { forwardRef } from "react";
import SvgJSIcon from "./JSIcon";

export const JSIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgJSIcon ref={ref} {...props} />;
  },
);
