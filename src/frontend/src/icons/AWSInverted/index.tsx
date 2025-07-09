import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import SvgAWS from "./AWS";

export const AWSInvertedIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <SvgAWS ref={ref} isdark={isdark} {...props} />;
});
