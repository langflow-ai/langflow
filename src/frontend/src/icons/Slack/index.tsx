import React, { forwardRef } from "react";
import { ReactComponent as SlackSVG } from "./slack-icon.svg";

export const SlackIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SlackSVG ref={ref} {...props} />;
  }
);
