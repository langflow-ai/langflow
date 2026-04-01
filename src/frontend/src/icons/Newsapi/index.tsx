import React, { forwardRef } from "react";
import NewsapiIconSVG from "./newsapi";

export const NewsapiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <NewsapiIconSVG ref={ref} {...props} />;
});
