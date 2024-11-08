import React, { forwardRef } from "react";
import SvgYoutube from "./SvgYoutube";

export const Youtube = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgYoutube className="icon" ref={ref} {...props} />;
  },
);
