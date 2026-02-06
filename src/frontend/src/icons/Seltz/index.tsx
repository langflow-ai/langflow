import type React from "react";
import { forwardRef } from "react";
import SvgSeltz from "./Seltz";

export const SeltzIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgSeltz ref={ref} {...props} />;
  },
);
