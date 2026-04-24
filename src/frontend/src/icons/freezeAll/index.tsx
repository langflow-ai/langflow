import type React from "react";
import { forwardRef } from "react";
import SvgFreezeAll from "./freezeAll";

export const freezeAllIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ className?: string }>
>((props, ref) => {
  return <SvgFreezeAll ref={ref} {...props} />;
});
