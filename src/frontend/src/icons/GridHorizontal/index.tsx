import { forwardRef } from "react";
import SVGGridHorizontalIcon from "./GridHorizontalIcon";

export const GridHorizontalIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SVGGridHorizontalIcon ref={ref} {...props} />;
});
