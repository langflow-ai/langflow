import React, { forwardRef } from "react";
import { ReactComponent as MetaSVG } from "./meta-icon.svg";

export const MetaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <MetaSVG ref={ref} {...props} />;
  }
);
