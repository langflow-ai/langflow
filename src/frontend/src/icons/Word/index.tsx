import React, { forwardRef } from "react";
import SvgWord from "./Word";

export const WordIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgWord ref={ref} {...props} />;
  },
);
