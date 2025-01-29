import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgNovita from "./novita";

export const NovitaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();

  return <SvgNovita ref={ref} {...props} isdark={isdark} />;
});
