import React, { forwardRef } from "react";
import BrevoIconSVG from "./brevo";

export const BrevoIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <BrevoIconSVG ref={ref} {...props} />;
  },
);
