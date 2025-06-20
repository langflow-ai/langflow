import React, { forwardRef } from "react";
import GridGainSVG from "./GridGain";

export const GridGainIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement>
>((props, ref) => <GridGainSVG ref={ref} {...props} />);
