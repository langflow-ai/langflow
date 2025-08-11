import type React from "react";
import { forwardRef } from "react";
import SvgGitLoader from "./GitLoader";

export const GitLoaderIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGitLoader ref={ref} {...props} />;
});
