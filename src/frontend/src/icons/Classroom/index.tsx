import React, { forwardRef } from "react";
import ClassroomIconSVG from "./classroom";

export const ClassroomIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ClassroomIconSVG ref={ref} {...props} />;
});
