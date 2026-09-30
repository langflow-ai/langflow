import React, { forwardRef } from "react";
import SvgAWS from "./AWS";

export const AWSIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgAWS ref={ref} {...props} />;
  },
);
