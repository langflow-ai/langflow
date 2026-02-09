import React, { forwardRef } from "react";
import GithubIconSVG from "./github";

export const GithubIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GithubIconSVG ref={ref} {...props} />;
});
