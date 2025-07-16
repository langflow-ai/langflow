import React, { forwardRef } from "react";
import XAISVG from "./xAIIcon.jsx";

export const XAIIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <XAISVG ref={ref} {...props} />;
  },
);
