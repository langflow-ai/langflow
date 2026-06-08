import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import NextPlaidIconSVG from "./NextPlaidIcon";

export const NextPlaidIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<object>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <NextPlaidIconSVG ref={ref} isdark={isdark} {...props} />;
});

export default NextPlaidIcon;
