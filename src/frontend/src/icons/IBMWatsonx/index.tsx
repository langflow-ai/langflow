import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgWatsonxAI from "./WatsonxAI";

export const WatsonxAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <SvgWatsonxAI ref={ref} isdark={isdark} {...props} />;
});
