import React, { forwardRef } from "react";
import KlaviyoIconSVG from "./klaviyo";

export const KlaviyoIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <KlaviyoIconSVG ref={ref} {...props} />;
});
