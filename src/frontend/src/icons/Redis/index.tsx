import type React from "react";
import { forwardRef } from "react";
import { SvgRedis } from "./Redis";

export const RedisIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgRedis ref={ref} {...props} />;
  },
);
