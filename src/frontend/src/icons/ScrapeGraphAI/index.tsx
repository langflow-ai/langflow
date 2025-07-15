import type React from "react";
import { forwardRef } from "react";
import ScrapeGraphAI from "./ScrapeGraphAI";

export const ScrapeGraph = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ScrapeGraphAI ref={ref} {...props} />;
});
