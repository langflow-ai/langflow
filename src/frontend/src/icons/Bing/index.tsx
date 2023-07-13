import React, { forwardRef } from "react";
import { ReactComponent as BingSVG } from "./bing.svg";

export const BingIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <BingSVG ref={ref} {...props} />;
  }
);
