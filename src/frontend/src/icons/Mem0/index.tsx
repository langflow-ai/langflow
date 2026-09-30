import React, { forwardRef } from "react";
import SvgMem from "./SvgMem";

export const Mem0 = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgMem className="icon" ref={ref} {...props} />;
  },
);
