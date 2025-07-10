import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import AstraSVG from "./AstraDB";

export const AstraDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <AstraSVG ref={ref} isdark={isdark} {...props} />;
});
