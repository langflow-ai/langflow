import React from "react";
import * as LucideIcons from "lucide-react";

/*
How to use this component:

import Icon from "@site/src/components/icon";

<Icon name="AlertCircle" size={24} color="red" />
*/

type IconProps = {
  name: string;
};

export default function Icon({ name, ...props }: IconProps) {
  const Icon = LucideIcons[name];
  return Icon ? <Icon {...props} /> : null;
}
