import type React from "react";
import { forwardRef } from "react";
import SvgSerpSearchAPI from "./SerpSearch";

export const SerpSearchIconComposio = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSerpSearchAPI ref={ref} {...props} />;
});
