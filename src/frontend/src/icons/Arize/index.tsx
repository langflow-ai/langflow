import type React from "react";
import { forwardRef } from "react";
import SvgArize from "./Arize";

export const ArizeIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgArize ref={ref} {...props} />;
  },
);
