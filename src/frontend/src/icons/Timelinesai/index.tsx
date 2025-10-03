import React, { forwardRef } from "react";
import TimelinesaiIconSVG from "./timelinesai";

export const TimelinesaiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <TimelinesaiIconSVG ref={ref} {...props} />;
});
