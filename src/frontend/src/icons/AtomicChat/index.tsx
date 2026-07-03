import type React from "react";
import { forwardRef } from "react";
import SvgAtomicChat from "./AtomicChatIcon";

export const AtomicChatIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAtomicChat ref={ref} {...props} />;
});
