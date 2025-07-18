import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import BWSvgPython from "./Python";

export const BWPythonIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark.toString());
  return <BWSvgPython ref={ref} {...props} isdark={isdark} />;
});
