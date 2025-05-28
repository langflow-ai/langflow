import React, { forwardRef } from "react";
import SvgExa from "./Exa";

export const ExaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgExa ref={ref} {...props} />;
  },
);
