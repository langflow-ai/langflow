import type React from "react";
import { forwardRef } from "react";
import SvgOutageDeck from "./outagedeck";

export const OutageDeckIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOutageDeck ref={ref} {...props} />;
});
