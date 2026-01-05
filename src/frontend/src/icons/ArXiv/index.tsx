import type React from "react";
import { forwardRef } from "react";
import SvgArXivIcon from "./ArXivIcon";

export const ArXivIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgArXivIcon ref={ref} {...props} />;
  },
);

export default ArXivIcon;
