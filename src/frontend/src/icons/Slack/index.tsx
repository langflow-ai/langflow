import React, { forwardRef } from "react";
import SvgSlackIcon from "./SlackIcon";

export const SlackIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgSlackIcon ref={ref} {...props} />;
  },
);
