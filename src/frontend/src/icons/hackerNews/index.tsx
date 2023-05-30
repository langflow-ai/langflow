import React, { forwardRef } from "react";
import { ReactComponent as HackerNewsSVG } from "./Y_Combinator_logo.svg";

export const HackerNewsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <HackerNewsSVG ref={ref} {...props} />;
});
