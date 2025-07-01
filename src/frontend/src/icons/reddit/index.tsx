import React, { forwardRef } from "react";
import RedditIconSVG from "./reddit";

export const RedditIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <RedditIconSVG ref={ref} {...props} />;
});