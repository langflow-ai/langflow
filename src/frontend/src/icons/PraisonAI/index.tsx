import type React from "react";
import { forwardRef } from "react";
import SvgPraisonAiIcon from "./PraisonAiIcon";

export const PraisonAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPraisonAiIcon ref={ref} {...props} />;
});
