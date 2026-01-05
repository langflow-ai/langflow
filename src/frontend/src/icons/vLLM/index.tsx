import type React from "react";
import { forwardRef } from "react";
import SvgVLLM from "./vLLM";

export const VllmIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgVLLM ref={ref} {...props} />;
  },
);
