import type React from "react";
import { forwardRef } from "react";
import SvgAliyun from "./Aliyun";

export const AliyunIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAliyun ref={ref} {...props} />;
});
