import type React from "react";
import { forwardRef } from "react";
import Plivo from "./Plivo";

export const PlivoIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <Plivo ref={ref} {...props} />;
  },
);
