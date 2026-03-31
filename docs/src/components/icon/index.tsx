import React from "react";
import clsx from "clsx";
import * as LucideIcons from "lucide-react";

/*
How to use this component:

import Icon from "@site/src/components/icon";

<Icon name="AlertCircle" size={24} color="red" />
*/

type IconProps = React.ComponentProps<LucideIcons.LucideIcon> & {
  name: string;
};

export default function Icon({
  name,
  size = 16,
  className,
  ...props
}: IconProps) {
  const LucideIcon = LucideIcons[name as keyof typeof LucideIcons] as
    | React.FC<React.ComponentProps<LucideIcons.LucideIcon>>
    | undefined;
  if (!LucideIcon) return null;

  const hasAccessibleName =
    "aria-label" in props ||
    "aria-labelledby" in props ||
    ("title" in props && Boolean(props.title));

  return (
    <LucideIcon
      size={size}
      className={clsx("lf-inline-icon", className)}
      aria-hidden={hasAccessibleName ? undefined : true}
      focusable={hasAccessibleName ? undefined : false}
      role={hasAccessibleName ? undefined : "presentation"}
      {...props}
    />
  );
}
