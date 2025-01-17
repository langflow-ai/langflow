import React, { forwardRef } from "react";
import SvgSolana from "./Solana";

export const SolanaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ color?: string }>
>((props, ref) => {
  return <SvgSolana ref={ref} {...props} />;
});
