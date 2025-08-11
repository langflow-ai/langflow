import type React from "react";
import { forwardRef } from "react";
import SvgAzLogo from "./AzLogo";

export const AzIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgAzLogo ref={ref} {...props} />;
  },
);
