import React, { forwardRef } from "react";
import KlipfolioIconSVG from "./klipfolio";

export const KlipfolioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <KlipfolioIconSVG ref={ref} {...props} />;
});
