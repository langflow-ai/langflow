import type React from "react";
import { forwardRef } from "react";
import SvgHomeAssistant from "./HomeAssistant";

export const HomeAssistantIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgHomeAssistant ref={ref} {...props} />;
});
