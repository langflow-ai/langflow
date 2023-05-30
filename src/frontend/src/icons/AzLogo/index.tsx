import React, { forwardRef } from "react";
import { ReactComponent as AzSVG } from "./az_logo.svg";

export const AzIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <AzSVG ref={ref} {...props} />;
  }
);
