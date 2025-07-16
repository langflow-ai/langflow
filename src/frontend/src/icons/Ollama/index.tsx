import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import SvgOllama from "./Ollama";

export const OllamaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);

  return <SvgOllama ref={ref} {...props} color={isDark ? "#fff" : "#000"} />;
});
