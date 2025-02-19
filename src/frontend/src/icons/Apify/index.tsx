import React, { forwardRef } from "react";
import SvgApifyLogo from "./Apify";

export const ApifyIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgApifyLogo ref={ref} {...props} />;
  },
);
