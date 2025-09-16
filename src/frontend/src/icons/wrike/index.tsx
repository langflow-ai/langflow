import React, { forwardRef } from "react";
import WrikeIconSVG from "./wrike";

export const WrikeIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <WrikeIconSVG ref={ref} {...props} />;
  },
);
