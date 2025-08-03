import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import SentenceTransformersSVG from "./sentenceTransformers";

export const SentenceTransformersIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <SentenceTransformersSVG ref={ref} isdark={isdark} {...props} />;
});
