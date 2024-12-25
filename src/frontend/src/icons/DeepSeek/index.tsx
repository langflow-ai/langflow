import React, { forwardRef } from "react";
import SvgDeepSeekIcon from "./DeepSeekIcon";

export const DeepSeekIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgDeepSeekIcon ref={ref} {...props} />;
});

export default DeepSeekIcon;
