import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgJSIcon from "./JSIcon";

export const JSIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark.toString());
    return <SvgJSIcon ref={ref} {...props} isdark={isdark} />;
  },
);
