import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import ComposioIconSVG from "./composio";

export const ComposioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();

  return <ComposioIconSVG ref={ref} isdark={isdark} {...props} />;
});
