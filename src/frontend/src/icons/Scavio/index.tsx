import type React from "react";
import { forwardRef } from "react";
import Scavio from "./Scavio";

export const ScavioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ isDark?: boolean }>
>((props, ref) => {
  const { isDark, ...rest } = props;
  return <Scavio ref={ref} isdark={isDark?.toString()} {...rest} />;
});

ScavioIcon.displayName = "ScavioIcon";
