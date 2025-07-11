import type React from "react";
import { forwardRef } from "react";
import SvgStreamlit from "./SvgStreamlit";

export const Streamlit = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgStreamlit className="icon" ref={ref} {...props} />;
  },
);
