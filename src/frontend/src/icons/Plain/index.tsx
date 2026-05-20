import React, { forwardRef } from "react";
import PlainIconSVG from "./plain";

export const PlainIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <PlainIconSVG ref={ref} {...props} />;
  },
);
