import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import XAISVG from "./xAIIcon.jsx";

export const XAIIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark).toString();
    return <XAISVG ref={ref} isdark={isdark} {...props} />;
  },
);
