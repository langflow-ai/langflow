import type React from "react";
import { forwardRef } from "react";
import SvgCrewAiIcon from "./CrewAiIcon";

export const CrewAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCrewAiIcon ref={ref} {...props} />;
});
