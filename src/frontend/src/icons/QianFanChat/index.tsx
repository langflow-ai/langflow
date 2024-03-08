import React, { forwardRef } from "react";
import SvgQianFanChat from "./QianFanChat";

export const QianFanChatIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgQianFanChat ref={ref} {...props} />;
});
