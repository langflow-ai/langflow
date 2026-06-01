import type React from "react";
import { forwardRef } from "react";
import SvgBocha from "./Bocha";

export const BochaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgBocha ref={ref} {...props} />;
  },
);
