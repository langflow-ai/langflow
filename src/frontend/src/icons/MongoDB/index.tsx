import React, { forwardRef } from "react";
import { ReactComponent as SlackSVG } from "./mongodb-icon.svg";

export const MongoDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SlackSVG ref={ref} {...props} />;
});
