import React, { forwardRef } from "react";
import { ReactComponent as AnthropicSVG } from "./anthropic_box.svg";

export const AnthropicIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AnthropicSVG ref={ref} {...props} />;
});
