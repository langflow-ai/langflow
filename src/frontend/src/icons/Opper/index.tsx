import type React from "react";
import { forwardRef } from "react";
import SvgOpper from "./OpperIcon";

export const OpperIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgOpper ref={ref} {...props} />;
  },
);
