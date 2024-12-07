import React, { forwardRef } from "react";
import ThumbDownFilled from "./thumbDown";
import ThumbUpFilled from "./thumbUp";

export const ThumbUpIconCustom = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ThumbUpFilled ref={ref} {...props} />;
});

export const ThumbDownIconCustom = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ThumbDownFilled ref={ref} {...props} />;
});
