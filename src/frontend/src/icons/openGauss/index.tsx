import type React from "react";
import { forwardRef } from "react";
import OpenGaussSVG from "./openGauss";

export const openGaussIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ isDark?: boolean }>
>((props, ref) => <OpenGaussSVG ref={ref} {...props} />);
