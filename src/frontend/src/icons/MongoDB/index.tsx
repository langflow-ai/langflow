import React, { forwardRef } from "react";
import { ReactComponent as MongoDBSVG } from "./mongodb-icon.svg";

export const MongoDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MongoDBSVG ref={ref} {...props} />;
});
