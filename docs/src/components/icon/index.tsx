import React from "react";
import * as LucideIcons from "lucide-react";

// Import custom icons from the frontend - use them directly
import { McpIcon } from "../../../../src/frontend/src/icons/MCP";

/*
How to use this component:

import Icon from "@site/src/components/icon";

// Lucide icons (built-in)
<Icon name="AlertCircle" size={24} color="red" />
<Icon name="Plus" aria-hidden="true" />

// Custom Langflow icons - use them directly
<McpIcon aria-hidden="true" />

HOW TO ADD A CUSTOM ICON FROM THE FRONTEND LIBRARY:

1. Find the icon in the frontend library:
   - Look in `src/frontend/src/icons/` for available icons
   - Check `src/frontend/src/icons/eagerIconImports.ts` or `lazyIconImports.ts` for the exact export name

2. Import the icon in this file:
   import { McpIcon } from "../../../../src/frontend/src/icons/MCP";

3. Export it for use in documentation:
   export { McpIcon };

4. Use it directly in documentation:
   <McpIcon aria-hidden="true" />

Note: Import the icon and use it directly - no mapping needed!
*/

type IconProps = {
  name: string;
};

export default function Icon({ name, ...props }: IconProps) {
  // For now, only handle Lucide icons through the name prop
  // Custom icons should be imported and used directly
  const Icon = LucideIcons[name];
  return Icon ? <Icon {...props} /> : null;
}

// Export custom icons for direct use
export { McpIcon };