import React, { forwardRef } from "react";
import SvgOpenAi from "./OpenAi";

export const OpenAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOpenAi ref={ref} {...props} />;
});
