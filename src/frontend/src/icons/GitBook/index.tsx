import type React from "react";
import { forwardRef } from "react";
import SvgGitbookSvgrepoCom from "./GitbookSvgrepoCom";

export const GitBookIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGitbookSvgrepoCom ref={ref} {...props} />;
});
