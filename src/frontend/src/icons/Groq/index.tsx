import type React from "react";
import { forwardRef } from "react";
import SvgGroqLogo from "./GroqLogo";

export const GroqIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgGroqLogo ref={ref} {...props} />;
  },
);
