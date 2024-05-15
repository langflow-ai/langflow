import React, { forwardRef } from "react";
import SvgCouchbase from "./Couchbase";

export const CouchbaseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCouchbase ref={ref} {...props} />;
});
