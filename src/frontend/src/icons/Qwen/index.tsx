import React, { forwardRef } from "react";
import { SvgQwenLogo } from "./QwenLogo";

export const QwenIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgQwenLogo ref={ref} {...props} />;
  },
);
