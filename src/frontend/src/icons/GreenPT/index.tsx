import type React from "react";
import { forwardRef } from "react";
import SvgGreenPT from "./greenpt";

export const GreenPTIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => <SvgGreenPT ref={ref} {...props} />);
