import React, { forwardRef } from "react";
import {
  default as SvgBeautifulSoup,
  default as SvgYoutube,
} from "./SvgBeautifulSoup";

export const BeautifulSoup = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgBeautifulSoup className="icon" ref={ref} {...props} />;
});
