import React, { forwardRef } from "react";
import ThumbUpFilled from "./thumbUp";
import ThumbDownFilled from "./thumbDown";

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
