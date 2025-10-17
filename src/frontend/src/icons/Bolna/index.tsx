import React, { forwardRef } from "react";
import BolnaIconSVG from "./bolna";

export const BolnaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <BolnaIconSVG ref={ref} {...props} />;
  },
);
