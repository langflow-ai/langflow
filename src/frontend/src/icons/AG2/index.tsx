import type React from "react";
import { forwardRef } from "react";
import SvgAG2Icon from "./AG2Icon";

export const AG2Icon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgAG2Icon ref={ref} {...props} />;
  },
);
