import React, { forwardRef } from "react";
import NeonIconSVG from "./neon";

export const NeonIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <NeonIconSVG ref={ref} {...props} />;
  },
);
