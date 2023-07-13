import React, { forwardRef } from "react";
import { ReactComponent as SearxSVG } from "./Searx_logo.svg";

export const SearxIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SearxSVG ref={ref} {...props} />;
  }
);
