import React, { forwardRef } from "react";
import ExcelIconSVG from "./excel";

export const ExcelIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <ExcelIconSVG ref={ref} {...props} />;
  },
);
