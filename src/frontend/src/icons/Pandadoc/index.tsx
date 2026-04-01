import React, { forwardRef } from "react";
import PandadocIconSVG from "./pandadoc";

export const PandadocIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <PandadocIconSVG ref={ref} {...props} />;
});
