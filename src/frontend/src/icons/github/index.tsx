import type React from "react";
import { forwardRef } from "react";
import GithubIconSVG from "./github";

export const GithubIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GithubIconSVG ref={ref} {...props} />;
});
