import React, { forwardRef } from "react";
import { ReactComponent as MidjourneySVG } from "./Midjourney_Emblem.svg";

export const MidjourneyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MidjourneySVG ref={ref} {...props} />;
});
