import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import SvgNovita from "./novita";

export const NovitaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();

  return <SvgNovita ref={ref} {...props} isdark={isdark} />;
});
