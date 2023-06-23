import React, { forwardRef } from "react";
import { ReactComponent as SupabaseSvg } from "./supabase-icon.svg";

export const SupabaseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SupabaseSvg ref={ref} {...props} />;
});
