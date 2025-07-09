import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import SvgAnthropicBox from "./Anthropic";

export const AnthropicIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);

  return <SvgAnthropicBox ref={ref} {...props} isDark={isDark} />;
});
